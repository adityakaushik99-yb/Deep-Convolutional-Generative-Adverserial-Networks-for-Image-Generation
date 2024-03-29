import os.path
import numpy as np
import scipy.io
import scipy.ndimage as sn
import h5py

from util import log

__PATH__ = './datasets/fashion_mnist'

rs = np.random.RandomState(123)

class Dataset(object):

    def __init__(self, ids, name='default', max_examples=None, is_train=True):
        self._ids = list(ids)
        self.name = name
        self.is_train = is_train

        if max_examples is not None:
            self._ids = self._ids[:max_examples]

            filename = 'data.hy'

            file = os.path.join(__PATH__, filename)
            log.info("Reading %s...", file)

            self.data = h5py.File(file, 'r')
            log.info("Reading Done: %s", file)

    def get_data(self, id):
        m = self.data[id]['image'].value/255

        return m

    @property
    def ids(self):
        return self._ids
    
def __len__(self):
    return len(self.ids)

def __repr__(self):
    return 'Dataset (%s, %d examples)' %(self.name, len(self))

def get_data_info():
    return np.array([28,28,1])
def get_conv_info():
    return np.array([32, 64, 128])

def get_deconv_info():
    return np.array([[100,2,1], [25, 3, 2], [6, 4, 2], [1, 6, 2]])

def create_default_splits(is_train=True):
    ids = all_ids()
    n = len(ids)

    num_trains = 60000

    dataset_train = Dataset(ids[:num_trains], name='train', is_train=False)
    dataset_test = Dataset(ids[num_trains:], name='test', is_train=False)

    return dataset_train, dataset_test

def all_ids():
    id_filename = 'id.txt'

    id_txt = os.path.join(__PATH__, id_filename)

    with open(id_txt, 'r') as fp:
        _ids = [s.strip() for s in fp.readlines() if s]

        rs.shuffle(_ids)

    return _ids