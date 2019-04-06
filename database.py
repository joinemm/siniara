# Project: Fansite Bot
# File: database.py
# Author: Joinemm
# Date created: 06/04/19
# Python Version: 3.6

import sqlite3
from collections import namedtuple


SQLDATABASE = 'data/database.db'


def query(command, parameters=(), maketuple=False, default=None):
    connection = sqlite3.connect(SQLDATABASE)
    cursor = connection.cursor()
    cursor.execute(command, parameters)
    data = cursor.fetchall()
    if len(data) == 0:
        return default

    if maketuple:
        names = [description[0] for description in cursor.description]
        NT = namedtuple('Data', names)
        result = NT._make(data[0])
    else:
        result = data
    connection.close()
    return result


def execute(command, parameters=()):
    connection = sqlite3.connect(SQLDATABASE)
    cursor = connection.cursor()
    cursor.execute(command, parameters)
    connection.commit()
    connection.close()


def get_channel_settings(channel_id):
    data = query("SELECT text_posts, image_text, image_links FROM settings WHERE channel_id = ?", (channel_id,),
                 maketuple=True)
    if data is None:
        return namedtuple('Data', ['text_posts', 'image_text', 'image_links'])._make([1, 1, 0])
    return data


def get_channels(user_id):
    data = query("SELECT channel_id FROM follows WHERE user_id = ?", (user_id,), default=[])
    return [x[0] for x in data]


def get_user_ids():
    data = query("SELECT DISTINCT user_id FROM follows", default=[])
    return [str(x[0]) for x in data]


def add_follow(channel_id, user_id, username):
    execute("REPLACE INTO follows (channel_id, user_id, username) values (?, ?, ?)",
            (channel_id, user_id, username))


def remove_follow(channel_id, user_id):
    execute("DELETE FROM follows WHERE channel_id = ? and user_id = ?", (channel_id, user_id))


def follow_exists(channel_id, user_id):
    data = query("SELECT * FROM follows WHERE channel_id = ? and user_id = ?", (channel_id, user_id))
    if data is None:
        return False
    else:
        return True


def add_tweet(channel_id, user_id, images):
    execute("UPDATE follows SET tweets = tweets + 1, images = images + ? WHERE channel_id = ? and user_id = ?",
            (images, channel_id, user_id))


def change_setting(channel_id, setting, new_value):
    execute("insert or ignore into settings(channel_id) values(?)", (channel_id,))
    execute("update settings set %s = ?" % setting, (new_value,))


def get_user_data(user_id):
    data = query("SELECT username, tweets, images FROM follows WHERE user_id = ?", (user_id,))
    if data is None:
        return None
    username = data[0][0]
    tweets = 0
    images = 0
    for entry in data:
        tweets += entry[1]
        images += entry[2]
    return username, tweets, images
