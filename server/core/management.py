from . import main
from . import mypool
from config import settings


class ManagementUtility:
    """负责对用户输入的指令进行解析并调用相应的模块处理"""

    def __init__(self, sys_argv):
        self.sys_argv = sys_argv
        print(self.sys_argv)
        self.verify_argv()

    def verify_argv(self):
        """验证指令的合法性"""
        if len(self.sys_argv) < 2:
            self.help_msg()

        cmd = self.sys_argv[1]
        if not hasattr(self, cmd):
            print("invalid argument")
            self.help_msg()

    def help_msg(self):
        msg = """start  start FTP server"""
        exit(msg)

    def execute(self):
        """解析并执行指令"""
        func = getattr(self, self.sys_argv[1])
        func()

    def start(self):
        """启动FTP Server"""
        thread_pool = mypool.MyPool(settings.MAX_CONCURRENT_AMOUNT)
        server = main.FTPServer(self, thread_pool)  # 把向上thread_pool这个对象传入FTPServer进行实例化，让其成为一个全局变量
        server.run_forever()
