from __future__ import print_function
import multiprocessing
import threading

class Atomic(object):
    def __init__(self, _value, proc=False):
        self._value = _value
        self._type = type(_value)
        if proc:
            self.lock = multiprocessing.RLock()
        else:
            self.lock = threading.RLock()

    @property
    def value(self):
        self.lock.acquire()
        result = self._value
        self.lock.release()
        return result

    @value.setter
    def value(self, _value):
        if(not isinstance(_value, self._type)):
            raise TypeError("Cannot assign a different type of variable to value.")
        self.lock.acquire()
        self._value = _value
        self.lock.release()

    def atomic_get(self):
        return self.value

    def atomic_set(self, _value):
        self.value = _value

    def __str__(self):
        self.lock.acquire()
        res = str(self._value)
        self.lock.release()
        return res

