服务端启动： 
	在命令行输入：server.py start
客户端启动：
	在命令行输入：client.py -s 127.0.0.1 -P 9999

用户登录名：neo
密码：abc123

断点续传： 如果有未下载完成的文件，登录成功后会出现未完成列表，输入编号进行断点续传；退出断点续传输入“b”

上传、下载、从服务端删除文件和创建、删除目录应该先在服务端切换到相应的目录；

文件下载到“download”文件夹；上传文件时文件要先放入“upload”文件夹中

client发给server的指令有：
	1. dir
		1.1 只输入 dir，默认是打印 当前文件夹中的相关信息
		1.2 dir 有其他参数，则会在当前路径下拼接 dir后面的参数等到一个新路径
		
	2. cd 
		2.1 cd sub-path  会从当前目录切换到相应的子目录
		2.2 cd .. 或者 cd..\..  从当前目录返回上一层、上两层
		
	3. get filename  从当前目录下载文件
	
	4. put filename  把文件上传到当前目录
	
	5. mkdir sub-path  在当前目录下创建一个子路径
	
	6. rmdir sub-path  从当前目录下删除一个子路径
	
	7. rmfile file 从当前目录删除文件