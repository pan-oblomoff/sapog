import logging
import random
import re
import sqlite3
from sqlite3 import Error
from enum import Enum
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

users = {}
db = "data.db"
token = ""
default_message = "Питон сам в себя не вкатится!"
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)
updater = Updater(token, use_context=True)


class Commands(Enum):
    START_KICK = "SapogPinai"
    STOP_KICK = "SapogNePinai"
    HELP = "help"

    def __str__(self):
        return str(self.value)


class Storage:
    @staticmethod
    def create_connection(db_file):
        connection = None
        try:
            connection = sqlite3.connect(db_file)
            connection.execute("PRAGMA foreign_keys = ON")
        except Error as e:
            print(e)

        return connection

    @staticmethod
    def select_users(connection):
        result = []
        cursor = connection.cursor()
        cursor.execute(
            "SELECT username FROM users;"
        )
        rows = cursor.fetchall()
        for row in rows:
            result.append(row[0])
        return result

    @staticmethod
    def select_kicks_for_user(connection, username):
        result = []
        cursor = connection.cursor()
        cursor.execute(
            "SELECT message FROM kicks INNER JOIN users ON kicks.userId = users.id WHERE users.username = ?;",
            (username,)
        )
        rows = cursor.fetchall()
        for row in rows:
            result.append(row[0])
        return result

    @staticmethod
    def add_user(connection, user, kicks):
        add_user_query = "INSERT INTO users(username) VALUES(?);"
        add_kick_query = "INSERT INTO kicks(userId, message) VALUES(?, ?)"
        cursor = connection.cursor()
        cursor.execute(add_user_query, (user,))
        user_id = cursor.lastrowid
        for current in kicks:
            cursor.execute(add_kick_query, (user_id, current,))
        connection.commit()
        return

    @staticmethod
    def add_kicks(connection, username, kicks):
        select_user_query = "SELECT id FROM users WHERE username = ?"
        add_kick_query = "INSERT INTO kicks(userId, message) VALUES(?, ?)"
        cursor = connection.cursor()
        cursor.execute(select_user_query, (username,))
        user_id = cursor.fetchone()
        for current in kicks:
            cursor.execute(add_kick_query, (user_id[0], current,))
        connection.commit()
        return

    @staticmethod
    def delete_user(connection, user):
        query = 'DELETE FROM users WHERE username = ?'
        cursor = connection.cursor()
        cursor.execute(query, (user,))
        pass


class UserStats:

    def __init__(self, username, kicks_list=None):
        self.kicks = []
        self.username = username
        self.message_limit = 8
        self.current_messages = 0
        if kicks_list is not None:
            self.kicks.extend(kicks_list)
        connection = Storage.create_connection(db)
        with connection:
            stored_kicks = Storage.select_kicks_for_user(connection, username)
            self.kicks.extend(stored_kicks)
            if len(stored_kicks) == 0:
                Storage.add_user(connection, username, self.kicks)
            elif kicks_list is not None:
                def is_not_stored(record):
                    return record not in stored_kicks

                not_stored = list(filter(is_not_stored, kicks_list))
                if len(not_stored) > 0:
                    Storage.add_kicks(connection, username, not_stored)

    def add_kick_message(self, message):
        self.kicks.append(message)
        connection = Storage.create_connection(db)
        with connection:
            Storage.add_kicks(connection, self.username, [message])

    def delete_from_storage(self):
        connection = Storage.create_connection(db)
        with connection:
            Storage.delete_user(connection, self.username)

    def record_message(self):
        self.current_messages += random.randint(0, 3)

    def is_kickable(self):
        return self.current_messages >= self.message_limit

    def get_kick_message(self):
        if (len(self.kicks) == 0):
            raise Exception("No kick messages found for user " + self.username)
        index = random.randint(0, len(self.kicks) - 1)
        self.current_messages = 0
        return "@" + self.username + ", " + self.kicks[index]


def send_message(update, message):
    chat_id = update.message.chat_id
    updater.bot.send_message(chat_id, message)


def help(update, context):
    text = "Вкатывайся!\n"
    text += "/" + Commands.START_KICK.value + " - попросить Сапог пинать когда ты слишком часто какоешь в чатике\n"
    text += "/" + Commands.START_KICK.value + " message - попросить Сапог начать пинать с текстом message\n"
    text += "/" + Commands.STOP_KICK.value + " - попросить Сапог больше не пинать\n"
    text += "/" + Commands.HELP.value + " - этот текст"
    update.message.reply_text(text)


def start_kicking(update, context):
    sender = update.message.from_user.username
    text = update.message.text
    logger.info("Got request to start kicking from " + sender + " with text " + text)
    result = re.sub("/" + Commands.START_KICK.value + "(@\S+)?", "", text, flags=re.IGNORECASE).strip()
    if len(result) > 0:
        if sender in users:
            users[sender].add_kick_message(result)
            send_message(update, "Добавлено")
            return
        else:
            users[sender] = UserStats(sender, kicks_list=[result])
    else:
        if sender in users:
            send_message(update, "Уже пинаю")
            return
        else:
            users[sender] = UserStats(sender, [default_message])
    send_message(update, "Prepare ur anus!")


def stop_kicking(update, context):
    sender = update.message.from_user.username
    logger.info("Got request from " + sender + " to stop kicking")
    if sender in users:
        users[sender].delete_from_storage()
        users.pop(sender)
        send_message(update, "Не буду")
    else:
        send_message(update, "И так не пинаю")


def kick(update, context):
    sender = update.message.from_user.username
    logger.info("Got message from " + sender)
    if sender in users:
        instance = users[sender]
        if instance.is_kickable():
            send_message(update, instance.get_kick_message())
        else:
            instance.record_message()
    pass


def error(update, context):
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def main():
    connection = Storage.create_connection(db)
    with connection:
        stored_users = Storage.select_users(connection)
        for current in stored_users:
            users[current] = UserStats(current)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler(Commands.HELP.value, help))
    dispatcher.add_handler(CommandHandler(Commands.START_KICK.value, start_kicking))
    dispatcher.add_handler(CommandHandler(Commands.STOP_KICK.value, stop_kicking))
    dispatcher.add_handler(MessageHandler(Filters.text, kick))
    dispatcher.add_error_handler(error)
    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
