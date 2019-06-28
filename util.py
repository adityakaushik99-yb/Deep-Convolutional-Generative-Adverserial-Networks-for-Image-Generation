import logging
import os, os.path
from colorlog import ColoredFormatter

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

formatter = ColoredFormatter("%(log_color)s[%(asctime)s] %(message)s", datefmt=None, reset=True, log_colors={
	'DEBUG':'cyan',
	'INFO': 'white,bold',
	'INFOV':'cyan,bold',
	'WARNING': 'yellow',
	'ERROR': 'red,bold',
	'CRITICAL': 'red,bg_white'
	}, secondary_log_colors={},
	style='%')
ch.setFormatter(formatter)

log = logging.getLogger('attcap')
log.setLevel(logging.DEBUG)
log.handlers = []
log.propagate=False
log.addHandler(ch)

logging.addLevelName(logging.INFO+1, 'INFOV')

def _infov(self, msg, *args, **kwargs):
	self.log(logging.INFO+1, msg, *args, **kwargs)

logging.Logger.infov = _infov
