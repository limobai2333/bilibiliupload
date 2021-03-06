import os
import subprocess
import sys
import time

import streamlink
import youtube_dl

from engine.plugins import logger, Companion
from threading import Event
fake_headers = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:38.0) Gecko/20100101 Firefox/38.0 Iceweasel/38.2.1'
}


class DownloadBase:
    def __init__(self, fname, url, suffix=None):
        self.fname = fname
        self.url = url
        self.suffix = suffix

    def check_stream(self):
        logger.debug(self.fname)
        raise NotImplementedError()

    def download(self, filename):
        raise NotImplementedError()

    def run(self):
        try:
            logger.info('开始下载%s：%s' % (self.__class__.__name__, self.fname))
            self.start()
        except:
            logger.exception("Uncaught exception:")
        finally:
            logger.info('退出下载')

    def start(self):
        file_name = self.file_name
        if self.check_stream():
            file_name += "." + self.suffix
            retval = self.download(file_name)
            self.rename(file_name)
            if retval != 0:
                logger.debug('继续下载')
                self.start()
            else:
                logger.info('下载完成' + self.fname)

    @staticmethod
    def rename(file_name):
        try:
            os.rename(file_name + '.part', file_name)
            logger.debug('更名{0}为{1}'.format(file_name + '.part', file_name))
        except FileNotFoundError:
            logger.info('FileNotFoundError:' + file_name)
        except FileExistsError:
            os.rename(file_name + '.part', file_name)
            logger.info('FileExistsError:更名{0}为{1}'.format(file_name + '.part', file_name))

    @property
    def file_name(self):
        file_name = '%s%s' % (self.fname, str(time.time())[:10])
        return file_name


class YDownload(DownloadBase):
    # url_list = None

    def __init__(self, fname, url, suffix='flv'):
        super().__init__(fname, url, suffix)
        self.ydl_opts = {}

    def check_stream(self):
        try:
            self.get_sinfo()
            return True
        except youtube_dl.utils.DownloadError:
            logger.debug('%s未开播或读取下载信息失败' % self.fname)
            return False

    def get_sinfo(self):
        info_list = []
        with youtube_dl.YoutubeDL() as ydl:
            # cu = self.url.get(self.__class__.__name__)
            if self.url:
                info = ydl.extract_info(self.url, download=False)
            else:
                logger.debug('%s不存在' % self.__class__.__name__)
                return
            for i in info['formats']:
                info_list.append(i['format_id'])
            logger.debug(info_list)
        return info_list

    def download(self, filename):
        try:
            self.ydl_opts = {'outtmpl': filename}
            self.dl()
        except youtube_dl.utils.DownloadError:
            return 1
        return 0

    def dl(self):
        with youtube_dl.YoutubeDL(self.ydl_opts) as ydl:
            # ydl.download([self.url[self.__class__.__name__]])
            ydl.download([self.url])


class SDownload(DownloadBase):
    def __init__(self, fname, url, suffix='mp4'):
        super().__init__(fname, url, suffix)
        self.stream = None
        self.flag = Event()

    def check_stream(self):
        logger.debug(self.fname)
        try:
            streams = streamlink.streams(self.url)
            if streams:
                self.stream = streams["best"]
                fd = self.stream.open()
                fd.close()
                streams.close()
                return True
        except streamlink.StreamlinkError:
            return

    def download(self, filename):

        # fd = stream.open()
        try:
            with self.stream.open() as fd:
                with open(filename + '.part', 'wb') as file:
                    for f in fd:
                        file.write(f)
                        if self.flag.is_set():
                            # self.flag.clear()
                            return 1
                    return 0
        except OSError:
            self.rename(filename)
            raise
# class Monitoring(Timer):
#     def __init__(self, parent_pid, file_name):
#         super().__init__(func=self.kill_child_processes, interval=20)
#         self.parent = self.children = self.numc = None
#         self.parent_pid = parent_pid
#         self.file_name = file_name + '.part'
#         self.last_file_size = 0.0
#         self.flag = Event()
#
#     def terminate(self):
#         if self.numc == 0:
#             logger.error("ChildrenProcess doesn't exist")
#         else:
#             for process in self.children:
#                 process.terminate()
#             # logger.info('下载卡死' + self.file_name)
#
#     def get_process(self, parent_pid):
#         try:
#             parent = psutil.Process(parent_pid)
#         except psutil.NoSuchProcess:
#             self.stop()
#             return logger.error("Process doesn't exist")
#         children = parent.children(recursive=True)
#         numc = len(children)
#         logger.info(f'{parent}, {children}')
#         return parent, children, numc
#
#     def kill_child_processes(self):
#         if self.flag.is_set():
#             self.stop()
#             return
#         file_size = os.path.getsize(self.file_name) / 1024 / 1024 / 1024
#         if file_size <= self.last_file_size:
#             logger.error('下载卡死' + self.file_name)
#             if self.numc == 0:
#                 self.parent.terminate()
#             else:
#                 self.terminate()
#             time.sleep(1)
#             if os.path.isfile(self.file_name):
#                 return logger.info('卡死下载进程可能未成功退出')
#             else:
#                 self.stop()
#                 return logger.info('卡死下载进程成功退出')
#         self.last_file_size = file_size
#         if file_size >= 2.5:
#             self.flag.set()
#             self.terminate()
#             logger.info('分段下载' + self.file_name)
#
#     def __timer(self):
#         logger.debug('获取到{0}，{1}'.format(self.parent_pid, self.file_name))
#         retry = 0
#         while not self._flag.wait(self.interval):
#             self.parent, self.children, self.numc = self.get_process(self.parent_pid)
#             if os.path.isfile(self.file_name):
#                 self._func(*self._args, **self._kwargs)
#             else:
#                 logger.info('%s不存在' % self.file_name)
#                 if retry >= 2:
#                     self.terminate()
#                     return logger.info('结束进程，找不到%s' % self.file_name)
#                 retry += 1
#                 # logger.info('监控<%s>线程退出' % self.file_name)
#
#     def run(self):
#         try:
#             self.__timer()
#         finally:
#             logger.debug('退出监控<%s>线程' % self.file_name)


# ffmpeg.exe -i  http://vfile1.grtn.cn/2018/1542/0254/3368/154202543368.ssm/154202543368.m3u8
# -c copy -bsf:a aac_adtstoasc -movflags +faststart output.mp4
class FFmpegdl(DownloadBase):
    def __init__(self, fname, url, suffix=None):
        super().__init__(fname, url, suffix)
        self.raw_stream_url = None
        self.opt_args = []

    def download(self, filename):
        args = ['ffmpeg', '-headers', ''.join('%s: %s\r\n' % x for x in fake_headers.items()),
                '-y', '-i', self.raw_stream_url, '-bsf:a', 'aac_adtstoasc', *self.opt_args,
                '-c', 'copy', '-f', self.suffix, filename + '.part']
        proc = subprocess.Popen(args, stdin=subprocess.PIPE)
        monitor = Companion(proc.pid, filename, size=2.5)
        monitor.start()
        try:
            retval = proc.wait()
        except KeyboardInterrupt:
            if sys.platform != 'win32':
                proc.communicate(b'q')
            raise
        finally:
            monitor.stop()
        return retval
