import multiprocessing
import time
import engine
import common
from engine import CHECK, BE_MODIFIED, DOWNLOAD_UPLOAD, TO_MODIFY, UPLOAD, urls, url_status, url_status_base
from engine.downloader import download, sorted_checker
from common import logger
from common.event import Event
from engine.plugins.base_adapter import UploadBase
from engine.uploader import upload

# 初始化事件管理器
event_manager = common.event.EventManager()


@event_manager.register(DOWNLOAD_UPLOAD, block=True)
def process(name, url, mod):
    try:
        data = {"url": url, "date": common.time_now()}
        if mod == 'dl':
            p = multiprocessing.Process(target=download, args=(name, url))
            p.start()
            p.join()
            # download(name, url)
            upload("bilibili", name, data)
        elif mod == 'up':
            upload("bilibili", name, data)
        else:
            return url
    finally:
        return Event(BE_MODIFIED, args=(url,))


@event_manager.server(urls, url_status, url_status_base)
class KernelFunc:
    def __init__(self, _urls, _url_status, _url_status_base):
        self.urls = _urls
        self.url_status = _url_status
        self.url_status_base = _url_status_base
        self.batches, self.onebyone = sorted_checker(_urls)

    @event_manager.register(CHECK, block=True)
    def all_check(self):
        live = []
        try:
            for batch in self.batches:
                res = batch.check()
                if res:
                    live.extend(res)

            for single in self.onebyone:
                for url in single.url_list:

                    if single('检测' + url, url).check_stream():
                        live.append(url)

                    if url != single.url_list[-1]:
                        logger.debug('歇息会')
                        time.sleep(15)
        except IOError:
            logger.exception("IOError")
        finally:
            return Event(UPLOAD, args=(live,)), Event(TO_MODIFY, args=(live,))

    @event_manager.register(engine.TO_MODIFY)
    def modify(self, live_m):
        live_d = {}
        if live_m:
            event = []
            for live in live_m:
                if self.url_status[live] == 1:
                    logger.debug('已开播正在下载')
                else:
                    name = engine.find_name(live)
                    logger.debug(name + '刚刚开播，去下载')
                    event.append(Event(DOWNLOAD_UPLOAD, args=(name, live, 'dl')))

                live_d[live] = 1
            self.url_status.update(live_d)
            # url_status = {**url_status_base, **live_d}
            return tuple(event)

        else:
            logger.debug('无人直播')

    def free(self, list_url):
        status_num = list(map(lambda x: self.url_status.get(x), list_url))
        # if 1 in status_num or 2 in status_num:
        #     return False
        # else:
        #     return True
        return not (1 in status_num or 2 in status_num)

    @event_manager.register(engine.UPLOAD)
    def free_upload(self, _urls):
        logger.debug(_urls)
        event = []
        for title, v in engine.links_id.items():
            url = v[0]
            if self.free(v) and UploadBase.filter_file(title):
                event.append(Event(DOWNLOAD_UPLOAD, args=(title, url, 'up')))
                # self.event_manager.send_event(event_d)
                self.url_status[url] = 2
        return tuple(event)

    @event_manager.register(engine.BE_MODIFIED)
    def revise(self, url):
        if url:
            # 更新字典
            # url_status = {**url_status, **{url: 0}}
            self.url_status.update({url: 0})
