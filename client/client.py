import optparse
from socket import *
import struct
import json
import os
import shelve


class FTPClient:
    """FTP客户端"""
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    def __init__(self):
        self.username = None
        self.current_dir = None
        self.file_relative_path_in_server = None

        self.shelve_obj = shelve.open("%s\%s\suspended files" % (self.BASE_DIR, "download\\unfinished files"))

        parser = optparse.OptionParser()
        parser.add_option("-s", "--server", dest="server", help="ftp server ip_addr")
        parser.add_option("-P", "--port", type="int", dest="port", help="ftp server port")

        self.options, self.args = parser.parse_args()
        self.__args_verification()

        """建立链接"""
        self.__make_connection()

    def __args_verification(self):
        """判断输入的指令是否合法"""
        if not self.options.server or not self.options.port:
            exit("Error:must supply server and port parameter")

    def __make_connection(self):
        """创建socket链接"""
        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.connect((self.options.server, self.options.port))

    def __send_header(self, *args, **kwargs):
        header_dict = kwargs

        header_bytes = json.dumps(header_dict).encode("utf-8")
        header_length = struct.pack("i", len(header_bytes))

        self.socket.send(header_length)
        self.socket.send(header_bytes)

    def __recv_header(self):
        header_length_bytes = self.socket.recv(4)
        header_length = struct.unpack("i", header_length_bytes)[0]
        header_bytes = self.socket.recv(header_length)
        header_dict = json.loads(header_bytes.decode("utf-8"))
        return header_dict

    def auth(self):
        """用户认证"""
        count = 0
        while count < 3:
            username = input("username:").strip()
            if not username: continue
            password = input("password:").strip()
            if not password: continue

            self.__send_header(action="auth", username=username, password=password)
            res = self.__recv_header()
            if res.get("status_code") == 200:
                self.username = username
                self.current_dir = res.get("client_terminal_dir")
                print(res["status_msg"])
                return True
            else:
                print(res.get("status_msg"))
                count += 1

        if count == 3:
            exit("wrong username or password reached 3 times")

    def interactive(self):
        """deal with all the interactivity with FTP server"""
        if self.auth():
            self.__check_pending_files()
            while True:
                msg_input = input("%s >" % self.current_dir).strip()
                if not msg_input: continue
                cmd_list = msg_input.split()
                if hasattr(self, cmd_list[0]):
                    func = getattr(self, cmd_list[0])
                    func(cmd_list[1:])
                else:
                    print("invalid command")

    def __check_pending_files(self):
        """check whether suspended downloading files exists"""
        if self.shelve_obj.keys():
            print("test")
            while True:
                if not self.shelve_obj.keys():  # no suspended downloaded files exists after "reget" from server.
                    return
                for i, k in enumerate(self.shelve_obj.keys()):
                    file_path = os.path.join(self.BASE_DIR, "download", self.shelve_obj[k][0])
                    if os.path.exists(file_path):  # to check whether this suspended file is deleted manually or not.
                        recv_size = os.path.getsize(os.path.join(self.BASE_DIR, "download", self.shelve_obj[k][0]))
                        print("%s.  %s;  total size:%s;  received size:%s;  downloaded percent:%s" % (
                            i, k, self.shelve_obj[k][1], recv_size,
                            "{percent}".format(percent=int(recv_size / self.shelve_obj[k][1] * 100))))
                    else:  # if a unfinished file is deleted manually,this file info should be removed from the "suspended files".
                        del self.shelve_obj[k]

                # user input the code to choose which file to "reget"
                choice = input("select code to resume>>>").strip()
                if not choice: continue

                if choice.isdigit():
                    choice = int(choice)
                    if 0 <= choice < len(self.shelve_obj.keys()):
                        """shelve_obj.keys()[0] 需要list一下，即 list(shelve_obj.keys())[0]"""
                        file_select = list(self.shelve_obj.keys())[
                            choice]  # file_select is the file's relative path in server.
                        file_size_select = self.shelve_obj[file_select][1]
                        file_path_in_client = os.path.join(self.BASE_DIR, "download", self.shelve_obj[file_select][0])
                        recv_size = os.path.getsize(file_path_in_client)
                        self.__send_header(username=self.username, action="reget", file_select=file_select,
                                           file_size_select=file_size_select,
                                           recv_size=recv_size)
                        response = self.__recv_header()

                        # if this suspended file still exists in server,resume downloading from the break point.
                        if response.get("status_code") == 300:
                            rest_size = file_size_select - recv_size
                            with open(file_path_in_client, "ab") as f:
                                rest_recv_size = 0
                                # process_bar_generator = self.__process_bar(rest_size)
                                process_bar_generator = self.__process_bar(file_size_select)
                                process_bar_generator.__next__()

                                while rest_recv_size < rest_size:
                                    if (rest_size - rest_recv_size) < 1024:
                                        line = self.socket.recv(rest_size - rest_recv_size)
                                        f.write(line)
                                        rest_recv_size += len(line)
                                    else:
                                        line = self.socket.recv(1024)
                                        f.write(line)
                                        rest_recv_size += len(line)
                                    process_bar_generator.send(recv_size + rest_recv_size)
                                else:
                                    res = self.__recv_header()
                                    print("\n")
                                    if res.get("status_code") == 302:
                                        print(res.get("status_msg"))
                            os.replace(os.path.join(self.BASE_DIR, "download", self.shelve_obj[file_select][0]),
                                       os.path.join(self.BASE_DIR, "download", self.shelve_obj[file_select][2]))
                            del self.shelve_obj[
                                file_select]  # if "reget" successfully,delete this suspended file from "suspended files"
                        else:
                            print(response.get("status_msg"))
                    else:
                        print("operation code does not exist")
                else:  # choice is non-digit
                    if choice == "b":
                        break
                    else:
                        print("only number is valid")

    def __parameter_validity(self, args, min_args=None, max_args=None, exact_args=None):
        """check the validity of the number of cmd args"""
        if min_args:
            if len(args) < min_args:
                print("at least %s parameters needed while %s provided" % (min_args, len(args)))
                return False
        if max_args:
            if len(args) > max_args:
                print("at most %s parameters needed while %s provided" % (max_args, len(args)))
                return False
        if exact_args:
            if len(args) != exact_args:
                print("%s parameters exactly needed while %s provided" % (exact_args, len(args)))
                return False
        return True

    def __process_bar(self, total_size):
        """the generator of printing process bar called when "put" or "get" """
        last_percent = 0
        while True:
            process_size = yield last_percent
            process_percent = int((process_size / total_size) * 100)

            if process_percent > last_percent:
                print(">" * int(process_percent / 2) + "{percent}%".format(percent=process_percent), end="\r",
                      flush=True)
                last_percent = process_percent

    def get(self, cmd_args):
        """download file from ftp server"""
        # check the validity of cmd_args
        if self.__parameter_validity(cmd_args, min_args=1):
            """
            1. 拿到文件名
            2. 发送到服务端
            3. 等待服务端返回消息
                3.1 文件存在，拿到文件大小
                    3.1.1 循环接收文件
                3.2 文件不存在，print status_msg
            """
            filename = cmd_args[0]
            self.__send_header(username=self.username, action="get",
                               filename=filename)  # send the dict_type header containing filename and action type of "get" to ftp server
            response = self.__recv_header()
            if response.get("status_code") == 300:
                file_size = response.get("total_size")

                self.file_relative_path_in_server = os.path.join(self.current_dir,
                                                                 filename)  # record the the file's relative path in server in case of resuming from break point.
                self.shelve_obj[self.file_relative_path_in_server] = ["%s.unfinished" % filename, file_size, filename]

                process_bar_generator = self.__process_bar(file_size)
                process_bar_generator.__next__()

                with open(os.path.join(self.BASE_DIR, "download", "%s.unfinished") % filename, "wb") as f:
                    recv_size = 0
                    while recv_size < file_size:
                        if (file_size - recv_size) < 1024:  # final receive
                            line = self.socket.recv(file_size - recv_size)
                        else:
                            line = self.socket.recv(1024)
                        f.write(line)
                        recv_size += len(line)
                        process_bar_generator.send(recv_size)
                    else:
                        get_res = self.__recv_header()
                        if get_res.get("status_code") == 302:
                            del self.shelve_obj[self.file_relative_path_in_server]
                            print("\n")
                            print(get_res.get("status_msg").center(50, "-"))
                os.replace(("%s\%s\%s.unfinished") % (self.BASE_DIR, "download", filename),
                           ("%s\%s\%s") % (self.BASE_DIR, "download", filename))
            else:
                print(response.get("status_msg"))

    def put(self, cmd_args):
        """upload file to ftp server"""
        if self.__parameter_validity(cmd_args, exact_args=1):
            file_relative_path = cmd_args[0]
            full_path = os.path.join(self.BASE_DIR, "upload", file_relative_path)
            if not os.path.isfile(full_path):
                print("file uploaded not exist")
            else:  # file uploaded exists

                filename = file_relative_path.split("\\")[0]
                total_size = os.path.getsize(full_path)
                self.__send_header(username=self.username, action="put", filename=filename, total_size=total_size)

                process_bar_generator = self.__process_bar(total_size)
                process_bar_generator.__next__()

                with open(full_path, "rb") as f:
                    size_put = 0
                    for line in f:
                        self.socket.send(line)
                        size_put += len(line)
                        process_bar_generator.send(size_put)
                    else:
                        response = self.__recv_header()
                        if response.get("status_code") == 303:
                            print("\n")
                            print(response.get("status_msg").center(50, "-"))
                        else:
                            print("\n")
                            print(response.get("status_msg").center(50, "-"))

    def dir(self, cmd_args):  # cmd_args is a list containing the cmd arguments only.
        """show all the sub-folders and sub-files in this directory"""
        if not cmd_args:  # cmd_args is [], e.g. cmd is "dir"
            self.__send_header(username=self.username, action="dir", file_path=None)
        else:  # cmd_args list is not empty, e.g. cmd is "dir audio" or "dir docs\os" etc
            file_path = cmd_args[0]
            self.__send_header(username=self.username, action="dir", file_path=file_path)

        response = self.__recv_header()
        total_size = response.get("total_size")

        # receive the bytes of dir info
        recv_size = 0
        recv_bytes = b""
        while recv_size < total_size:
            if (total_size - recv_size) < 1024:
                line = self.socket.recv(total_size - recv_size)
                recv_bytes += line
                recv_size += len(line)
            else:
                line = self.socket.recv(1024)
                recv_bytes += line
                recv_size += len(line)
        print(recv_bytes.decode("gbk"))

    def cd(self, cmd_args):  # cd docs\os
        """change directory"""
        if self.__parameter_validity(cmd_args,
                                     exact_args=1):  # the cmd_args of the cd func requires one parameters exactly, e.g. ["docs\os"]
            self.__send_header(username=self.username, action="cd", target_dir=cmd_args[0])

            response = self.__recv_header()
            if response.get("status_code") == 350 or response.get("status_code") == 352:
                self.current_dir = response.get("client_terminal_dir")
                print(response.get("status_msg"))
            else:
                print(response.get("status_msg"))

    def __handle_dir(self, cmd_args, action_type):
        """mutual function called by func mkdir,rmdir and rmfile"""
        if self.__parameter_validity(cmd_args, exact_args=1):
            file_path = cmd_args[0]
            self.__send_header(username=self.username, action=action_type, file_path=file_path)
            response = self.__recv_header()
            print(response.get("status_msg"))

    def mkdir(self, cmd_args):
        """make a new directory"""
        self.__handle_dir(cmd_args, "mkdir")

    def rmdir(self, cmd_args):
        """remove a dir"""
        self.__handle_dir(cmd_args, "rmdir")

    def rmfile(self, cmd_args):
        """delete a file"""
        self.__handle_dir(cmd_args, "rmfile")


if __name__ == "__main__":
    client = FTPClient()
    client.interactive()
