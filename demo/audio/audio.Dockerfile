FROM ubuntu:20.04
MAINTAINER author "https://github.com/m986883511"
WORKDIR /m986883511
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update
RUN apt install wget file curl vim procps lsof -y
RUN apt install python3 python3-pip -y
RUN apt install ffmpeg alsa-base alsa-utils libasound-dev libportaudio2 libportaudiocpp0 portaudio19-dev usbutils -y --fix-missing

COPY test.wav .
# USER 1000
CMD  [ "ffplay", "-nodisp", "-autoexit", "test.wav" ]