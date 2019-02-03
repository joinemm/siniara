# Project: Joinemm-Bot
# File: database.py
# Author: Joinemm
# Date created: 02/02/19
# Python Version: 3.6

# modified version of Miso bot database

import json
from functools import reduce


class Datafile:

    def __init__(self, path):
        self.path = path
        self.data = self.read()

    def get_data(self):
        return self.data

    def set_data(self, keys, value, increment):
        path_to = reduce(create_key, keys[:-1], self.get_data())
        if isinstance(path_to, list):
            key = int(keys[-1])
        else:
            key = keys[-1]
        if increment and key in path_to:
            path_to[key] += value
        else:
            path_to[key] = value
        self.write()

    def append_data(self, keys, value, duplicate):
        path_to = reduce(create_key, keys[:-1], self.get_data())
        if duplicate is False and value in path_to:
            return False
        if keys[-1] in path_to:
            path_to[keys[-1]].append(value)
        else:
            path_to[keys[-1]] = [value]
        self.write()
        return True

    def delete_data(self, keys, value):
        path_to = reduce(create_key, keys, self.get_data())
        if isinstance(path_to, list):
            try:
                path_to.remove(value)
                self.write()
                return True
            except ValueError:
                return False
        elif isinstance(path_to, dict):
            try:
                del path_to[value]
                self.write()
                return True
            except KeyError:
                return False

    def del_data(self, keys):
        path_to = reduce(create_key, keys[:-1], self.get_data())
        try:
            del path_to[keys[-1]]
            self.write()
            return True
        except KeyError:
            return False

    def sort(self):
        self.data = order_dict(self.data)

    def read(self):
        with open(self.path, 'r') as filehandle:
            return json.load(filehandle)

    def write(self):
        with open(self.path, 'w') as filehandle:
            json.dump(self.data, filehandle, indent=4)


class Database:

    def __init__(self):
        self.datafiles = {"follows": Datafile('data/follows.json'),
                          "config": Datafile('data/config.json')}

    def get_attr(self, database, attr, default=None):
        datafile = self.datafiles[database]
        if attr == ".":
            return datafile.get_data()
        else:
            return deep_get(datafile.get_data(), attr, default)

    def set_attr(self, database, attr, value, increment=False):
        datafile = self.datafiles[database]
        keys = attr.split(".")
        datafile.set_data(keys, value, increment)
        return True

    def append_attr(self, database, attr, value, duplicate=True):
        datafile = self.datafiles[database]
        keys = attr.split(".")
        return datafile.append_data(keys, value, duplicate)

    def delete_attr(self, database, attr, value):
        datafile = self.datafiles[database]
        keys = attr.split(".")
        return datafile.delete_data(keys, value)

    def delete_key(self, database, attr):
        datafile = self.datafiles[database]
        keys = attr.split(".")
        return datafile.del_data(keys)


def create_key(d, key):
    if key not in d:
        d[key] = {}
    return d.get(key)


def deep_get(dictionary, keys, default=None):
    def getter(d, key):
        try:
            return d.get(key, default)
        except AttributeError:
            try:
                return d[int(key)]
            except (ValueError, IndexError):
                return default

    return reduce(getter, keys.split("."), dictionary)


def order_dict(data):
    result = {}
    for k, v in sorted(data.items()):
        if isinstance(v, dict):
            result[k] = order_dict(v)
        else:
            result[k] = v
    return result
