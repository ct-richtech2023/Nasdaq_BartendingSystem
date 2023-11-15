# 服务端
import socket
import os

serverAddr = './uds_socket3.txt'  # 套接字存放路径及名称
while True:
    # 地址复用
    if os.path.exists(serverAddr):
        os.unlink(serverAddr)

    # 创建socket
    # 注意TCP协议对应的为SOCK_STREAM 流式
    server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    server_sock.bind(serverAddr)

    # 让服务端的socket开启监听，等待客户端的连接请求
    # listen中的参数表示已经建立链接和半链接的总数
    # 如果当前已建立链接数和半链接数已达到设定值，那么新客户端不会立即connect成功，而是等待服务器能够处理时
    server_sock.listen(128)

    # 使用accept方法接收客户端的连接请求
    # 如果有新的客户端来连接服务器，那么就产生一个新的套接字专门为这个客户端服务
    # client_sock用来为这个客户端服务，与客户端形成一对一的连接
    # 而server_sock就可以省下来专门等待其他新客户端的连接请求
    # client_addr是请求连接的客户端的地址信息，为元祖，包含用户的IP和端口
    client_sock, client_addr = server_sock.accept()
    print("客户端%s:%s进行了连接!" % (client_sock, client_addr))

    # recv()方法可以接收客户端发送过来的数据，指明最大收取1024个字节的数据
    recv_data = client_sock.recv(1024)
    # python3中收到的数据为bytes类型
    # recv_data.decode()将bytes类型转为str类型
    print("接收到的数据为：", recv_data.decode())

    # send()方法向客户端发送数据，要求发送bytes类型的数据
    client_sock.send("thank you!\n".encode())

    # 关闭与客户端连接的socket
    # 只要关闭了，就意味着为不能再为这个客户端服务了，如果还需要服务，只能再次重新连接
    # client_sock.close()
    # 关闭服务端的监听socket
    # 要这个套接字关闭了，就意味着整个程序不能再接收任何新的客户端的连接
    # server_sock.close()