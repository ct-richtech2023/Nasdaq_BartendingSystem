FROM ubuntu:20.04
MAINTAINER author "https://github.com/m986883511"
WORKDIR  /home/adam
EXPOSE 22
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update
RUN apt install wget file curl vim procps lsof -y
RUN apt install openssh-server -y
RUN apt install vlc -y

RUN echo 'PermitRootLogin yes' >> /etc/ssh/sshd_config \
&& echo "X11Forwarding yes" >> /etc/ssh/sshd_config \
&& echo "X11UseLocalhost no" >> /etc/ssh/sshd_config \
&& mkdir /var/run/sshd

RUN apt install python3 python3-pip -y
RUN pip3 install python-vlc

COPY test.wav .
RUN useradd -u 8877 adam
USER adam
# RUN echo 'adam:adam' | chpasswd
# CMD ["/usr/sbin/sshd", "-D"]