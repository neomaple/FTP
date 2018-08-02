from config import settings
from socket import *
from .logger import Logger
import json
import struct
import hashlib
import configparser
import os
import subprocess


class FTPServer:
    """处理与客户端所有交互的socket server"""

    STATUS_CODE = {
        200: "pass authentication",
        201: "wrong username or password",
        300: "file exists",
        301: "file not exists",
        302: "file downloaded successfully",
        303: "file uploaded successfully",
        304: "file deleted",
        305: "deleting file failed",
        350: "dir already changed",
        351: "target dir not exist",
        352: "returned to root dir",
        353: "new dir created",
        354: "creating new dir failed",
        355: "dir removed",
        356: "removing dir failed"
    }

    def __init__(self, management_instance, thread_pool):
        self.management_instance = management_instance
        self.thread_pool = thread_pool

        self.socket = socket(AF_INET, SOCK_STREAM)
        self.socket.bind((settings.HOST, settings.PORT))
        self.socket.listen(settings.MAX_LISTEN)
        self.logger = Logger("user_track").logger()

        self.user_info = {}
        self.user_home = {}
        self.user_current_dir = {}  # 三个空字典是全局变量，用于储存多用户的相关信息

    def run_forever(self):
        """启动socket server"""
        print("start FTP server on %s:%s".center(50, "-") % (settings.HOST, settings.PORT))

        while True:
            self.conn, self.client_addr = self.socket.accept()
            print("got a new connection from %s" % (self.client_addr,))

            thread = self.thread_pool.get_thread()  # 从线程池thread_pool中取出一个Thread对象
            t = thread(target=self.handler, args=(self.conn,))  # 利用Thread对象开启一个handler函数的新线程
            t.daemon = True
            t.start()

    def handler(self, conn):
        """处理与客户端所有指令的交互；用于解析指令类型"""
        while True:
            try:
                header_dict = self.__recv_header(conn)
                username = header_dict["username"]
                print(header_dict)
                action_type = header_dict["action"]
                if action_type:  # 用于判断action type是否存在
                    if hasattr(self, action_type):
                        func = getattr(self, action_type)
                        func(conn, header_dict)
            except:
                conn.close()
                self.user_info.pop(username)
                self.user_home.pop(username)
                self.user_current_dir.pop(username)  # 某个客户端退出后，把其相关信息从相关字典中删除
                self.thread_pool.add_thread()  # 某个客户端退出后，需要再往队列中添加一个 Thread 对象
                break

    def __send_header(self, *args, **kwargs):
        """封装好、用于发送报头的函数"""
        conn = args[0]
        header_dict = kwargs

        header_bytes = json.dumps(header_dict).encode("utf-8")
        header_length = struct.pack("i", len(header_bytes))

        conn.send(header_length)
        conn.send(header_bytes)

    def __recv_header(self, conn):
        """封装好、用于接收字典报头的函数"""
        header_length_bytes = conn.recv(4)

        header_length = struct.unpack("i", header_length_bytes)[0]
        header_bytes = conn.recv(header_length)
        header_dict = json.loads(header_bytes.decode("utf-8"))
        return header_dict

    def auth(self, conn, header_dict):
        """处理用户认证请求"""
        config = configparser.ConfigParser()
        config.read(settings.ACCOUNT_FILE)
        username = header_dict["username"]
        user_password = header_dict["password"]

        m = hashlib.md5()
        m.update(user_password.encode("utf-8"))

        if username in config.sections():
            user_info = config.items(username)
            if m.hexdigest() == user_info[1][1]:
                """登录认证成功后，把数据库中的用户信息、用户根目录和用户当前所在的路径添加到相应的全局变量字典中，
                并把客户端终端显示的路径名返回给客户端"""

                self.user_info[username] = user_info
                self.user_home[username] = os.path.join(settings.USER_HOME_DIR, username)
                self.user_current_dir[username] = os.path.join(settings.USER_HOME_DIR, username)

                self.__send_header(conn, status_code=200, status_msg=self.STATUS_CODE[200],
                                   client_terminal_dir="".join(self.user_current_dir[username].split("home\\")[1]))
                self.logger.info("%s just login" % username)

            else:
                self.__send_header(conn, status_code=201, status_msg=self.STATUS_CODE[201])
        else:
            self.__send_header(conn, status_code=201, status_msg=self.STATUS_CODE[201])

    def reget(self, conn, header_dict):
        """resume download from break point"""
        username = header_dict["username"]
        file_relative_path = header_dict["file_select"]
        file_total_size = header_dict["file_size_select"]
        recv_size = header_dict["recv_size"]

        file_abs_path = os.path.join(settings.USER_HOME_DIR,
                                     file_relative_path)  # get the real path of this selected file in server

        if os.path.isfile(file_abs_path):  # to check whether the selected file exists
            if os.path.getsize(
                    file_abs_path) == file_total_size:  # to check whether the file existing in server is same with the selected file via comparing files' size
                self.__send_header(conn,
                                   status_code=300)  # send header telling client this suspended file still exists.
                with open(file_abs_path, "rb") as f:
                    f.seek(recv_size)
                    for line in f:
                        conn.send(line)
                    else:
                        self.__send_header(conn, status_code=302, status_msg=self.STATUS_CODE[302])
                        self.logger.info("%s re-downloaded the file: %s" % (username, file_abs_path))
            else:
                self.__send_header(conn, status_code=301, status_msg=self.STATUS_CODE[301])
        else:
            self.__send_header(conn, status_code=301, status_msg=self.STATUS_CODE[301])

    def get(self, conn, header_dict):
        """download file from server"""
        username = header_dict["username"]
        filename = header_dict["filename"]
        file_path = os.path.join(self.user_current_dir[username], filename)
        if os.path.isfile(file_path):  # to check whether "file_path" is a file.
            total_size = os.path.getsize(file_path)
            self.__send_header(conn, status_code=300,
                               total_size=total_size)  # tell client the file to be downloaded exists.

            with open(file_path, "rb") as f:
                for line in f:
                    conn.send(line)
                else:
                    self.__send_header(conn, status_code=302, status_msg=self.STATUS_CODE[302])
                    self.logger.info("%s downloaded the file: %s" % (username, file_path))
        else:
            self.__send_header(conn, status_code=301, status_msg=self.STATUS_CODE[301])

    def put(self, conn, header_dict):
        """upload file from client to ftp server"""
        username = header_dict["username"]
        filename = header_dict["filename"]
        total_size = header_dict["total_size"]

        with open("%s\%s" % (self.user_current_dir[username], filename), "wb") as f:
            recv_size = 0
            while recv_size < total_size:
                if (total_size - recv_size) < 1024:
                    line = conn.recv(total_size - recv_size)
                    f.write(line)
                    recv_size += len(line)
                else:
                    line = conn.recv(1024)
                    f.write(line)
                    recv_size += len(line)
            else:
                self.__send_header(conn, status_code=303, status_msg=self.STATUS_CODE[303])
                self.logger.info(
                    "%s uploaded the file:%s" % (username, "%s\%s" % (self.user_current_dir[username], filename)))

    def dir(self, conn, header_dict):
        """show to client all the sub-folders and sub-files in this directory"""
        username = header_dict["username"]
        sub_path = header_dict["file_path"]
        if not sub_path:  # sub-path is None, e.g. "dir"
            cmd_obj = subprocess.Popen("dir %s" % self.user_current_dir[username], shell=True, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
        else:  # e.g. "dir audio"
            cmd_obj = subprocess.Popen("dir %s\%s" % (self.user_current_dir[username], sub_path), shell=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        stdout = cmd_obj.stdout.read()
        stderr = cmd_obj.stderr.read()

        total_size = len(stdout) + len(stderr)

        self.__send_header(conn, total_size=total_size)
        conn.send(stdout)
        conn.send(stderr)

    def cd(self, conn, header_dict):
        """change to corresponding directory as per the sub-path in header_dict received from client"""
        username = header_dict["username"]
        target_dir = header_dict["target_dir"]

        full_path = os.path.realpath(os.path.join(self.user_current_dir[username], target_dir))
        if os.path.isdir(full_path):
            if full_path.startswith(
                    self.user_home[username]):  # target dir is in user's root dir, e.g. ..server\home\neo\docs
                self.user_current_dir[username] = full_path
                client_terminal_dir = self.user_current_dir[username].split("%s\\" % settings.USER_HOME_DIR)[1]
                self.__send_header(conn, status_code=350, status_msg=self.STATUS_CODE[350],
                                   client_terminal_dir=client_terminal_dir)
            else:  # target dir is not in user's root dir, e.g. ..server
                self.user_current_dir[username] = self.user_home[username]
                # print(self.user_current_dir[username])
                client_terminal_dir = self.user_current_dir[username].split("%s\\" % settings.USER_HOME_DIR)[1]
                # print(client_terminal_dir)
                self.__send_header(conn, status_code=352, status_msg=self.STATUS_CODE[352],
                                   client_terminal_dir=client_terminal_dir)
        else:  # target dir not exists.
            self.__send_header(conn, status_code=351, status_msg=self.STATUS_CODE[351])

    def __os_cmd(self, header_dict, cmd_type):
        """mutual function calling operating system to process"""
        username = header_dict["username"]
        file_relative_path = header_dict["file_path"]
        cmd_obj = subprocess.Popen("%s %s\%s" % (cmd_type, self.user_current_dir[username], file_relative_path),
                                   shell=True,
                                   stderr=subprocess.PIPE)
        stderr = cmd_obj.stderr.read()
        return stderr

    def mkdir(self, conn, header_dict):
        """make a new dir"""
        res = self.__os_cmd(header_dict, "md")
        username = header_dict["username"]

        if not res:
            self.__send_header(conn, status_code=353, status_msg=self.STATUS_CODE[353])
            self.logger.info("%s created a new dir [%s] in dir [%s]" % (
                username, header_dict["file_path"], self.user_current_dir[username]))
        else:
            self.__send_header(conn, status_code=354, status_msg=self.STATUS_CODE[354])

    def rmdir(self, conn, header_dict):
        """remove a dir"""
        res = self.__os_cmd(header_dict, "rd /s /q")
        username = header_dict["username"]
        if not res:
            self.__send_header(conn, status_code=355, status_msg=self.STATUS_CODE[355])
            self.logger.info(
                "%s removed a dir:%s" % (
                    username, "%s\%s" % (self.user_current_dir[username], header_dict["file_path"])))
        else:
            self.__send_header(conn, status_code=355, status_msg=self.STATUS_CODE[355])

    def rmfile(self, conn, header_dict):
        """remove a file"""
        res = self.__os_cmd(header_dict, "del")
        username = header_dict["username"]

        if not res:
            self.__send_header(conn, status_code=304, status_msg=self.STATUS_CODE[304])
            self.logger.info(
                "%s deleted a file [%s] from %s" % (
                    username, header_dict["file_path"], self.user_current_dir[username]))
        else:
            self.__send_header(conn, status_code=305, status_msg=self.STATUS_CODE[305])
