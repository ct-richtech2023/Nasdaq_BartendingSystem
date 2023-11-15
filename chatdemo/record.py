import pyaudio
import numpy as np
from scipy import fftpack
import wave
import time


# 录音
# 录音必须安装portaudio模块，否则会报错
# http://portaudio.com/docs/v19-doxydocs/compile_linux.html

CHUNK = 1024  # 块大小
FORMAT = pyaudio.paInt16  # 每次采集的位数
CHANNELS = 1  # 声道数
RATE = 48000  # 采样率：每秒采集数据的次数


class MyRecord:
    def __init__(self, filename,  threshold=7000):
        self.output = filename  # 文件存放位置
        self.threshold = threshold
        self.p = pyaudio.PyAudio()
        print('channels={}'.format(CHANNELS))

        info = self.p.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')
        for i in range(0, numdevices):
            if (self.p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
                print("Input Device id ", i, " - ", self.p.get_device_info_by_host_api_device_index(0, i).get('name'))

        self.stream = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, input_device_index=0,  frames_per_buffer=CHUNK)
        self.stream.start_stream()
        self.stopped = False

    def record(self, record_time=0):
        # while not self.stream.is_stopped():
        self.stream.start_stream()
        print("* 录音中...")
        frames = []
        if record_time > 0:
            for i in range(0, int(RATE / CHUNK * record_time)):
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
        else:
            stopflag = 0
            stopflag2 = 0
            while True:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                # print('lllllllllll')
                rt_data = np.frombuffer(data, np.dtype('<i2'))
                # print(rt_data*10)
                # 傅里叶变换
                fft_temp_data = fftpack.fft(rt_data, rt_data.size, overwrite_x=True)
                fft_data = np.abs(fft_temp_data)[0:fft_temp_data.size // 2 + 1]

                # 测试阈值，输出值用来判断阈值
                print(sum(fft_data) // len(fft_data))

                # 判断麦克风是否停止，判断说话是否结束，# 麦克风阈值，默认7000
                if sum(fft_data) // len(fft_data) > self.threshold:
                    stopflag += 1
                else:
                    stopflag2 += 1
                oneSecond = int(RATE / CHUNK)*2
                if stopflag2 + stopflag > oneSecond:
                    if stopflag2 > oneSecond // 3 * 2:
                        break
                    else:
                        stopflag2 = 0
                        stopflag = 0
                frames.append(data)
        print("* 录音结束")
        self.stream.stop_stream()
        # self.stream.close()
        # self.p.terminate()
        # with wave.open(str(self.count) + self.output, 'wb') as wf:
        with wave.open(self.output, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
        # self.count += 1
            # self.stream.start_stream()
            # time.sleep(1)

    def stop(self):
        self.stream.stop_stream()
        self.stream.close()
        self.p.terminate()
        self.stopped = True


if __name__ == '__main__':
    # recording('ppp.mp3', time=5)  # 按照时间来录音，录音5秒
    test = MyRecord('ppp.mp3', 10000)
    test.record()  # 没有声音自动停止，自动停止
