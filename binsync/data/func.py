import os
import time
import typing

import toml

from .base import Base


class FunctionArgument:
    __slots__ = (
        "idx",
        "name",
        "type_str",
        "size"
    )

    def __init__(self, idx, name, type_str, size):
        self.idx = idx
        self.name = name
        self.type_str = type_str
        self.size = size

    def __getstate__(self):
        return dict(
            (k, getattr(self, k)) for k in self.__slots__
        )

    def __setstate__(self, state):
        for k in self.__slots__:
            setattr(self, k, state[k])

    def __eq__(self, other):
        if isinstance(other, FunctionArgument):
            for k in self.__slots__:
                if getattr(self, k) != getattr(other, k):
                    return False
            return True
        return False

    def dump(self):
        return toml.dumps(self.__getstate__())

    @classmethod
    def parse(cls, s):
        fa = FunctionArgument(None, None, None, None)
        fa.__setstate__(toml.loads(s))
        return fa


class Function(Base):
    __slots__ = (
        "addr",
        "name",
        "ret_type_str",
        "arguments",
        "notes",
        "last_change",
    )

    def __init__(self, addr, name=None, ret_type_str=None, arguments=None, notes=None, last_change=-1):
        self.addr = addr
        self.name = name
        self.ret_type_str = ret_type_str
        self.arguments: typing.Dict[int, FunctionArgument] = {} if not arguments else arguments
        self.notes = notes
        self.last_change = last_change

    def __getstate__(self):
        function_data = {
            "function_prototype": {
                "addr": self.addr,
                "name": self.name,
                "ret_type_str": self.ret_type_str,
                "notes": self.notes,
                "last_change": self.last_change
            }
        }
        for idx, arg in self.arguments.items():
            function_data.update({"%x" % idx: arg.__getstate__()})
        return function_data

    def __setstate__(self, state):
        if not isinstance(state["function_prototype"]["addr"], int):
            raise TypeError("Unsupported type %s for addr." % type(state["addr"]))

        for k in state.keys():
            if k == "function_prototype":
                self.addr = state[k]["addr"]
                self.name = state[k].get("name", None)
                self.ret_type_str = state[k].get("ret_type_str", None)
                self.notes = state[k].get("notes", None)
                self.last_change = state[k]["last_change"]
            else:
                self.arguments[int(k)] = FunctionArgument.parse(toml.dumps(state[k]))

    def __eq__(self, other):
        if isinstance(other, Function):
            return other.addr == self.addr \
                   and other.name == self.name \
                   and other.ret_type_str == self.ret_type_str \
                   and other.arguments == self.arguments \
                   and other.notes == self.notes
        return False

    def set_func_argument(self, arg_idx, arg_name, arg_type_str, arg_size):
        self.arguments[arg_idx] = FunctionArgument(arg_idx, arg_name, arg_type_str, arg_size)

    def dump(self):
        return self.__getstate__()

    @classmethod
    def parse(cls, s):
        func = Function(0)
        func.__setstate__(s)
        return func

    @classmethod
    def load(cls, func_toml):
        f = Function(0)
        f.__setstate__(func_toml)
        return f
