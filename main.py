import datetime
import logging
import os
import sqlite3
import pytz
from sqlite3 import Connection

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackContext, PollAnswerHandler

from constants import MOOD_ID_LOOKUP, mood_options, MESSAGES, COMMAND
from generation import mood_message

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def init_database() -> Connection:
    db = sqlite3.connect("./data.db")
    db.execute(
        "CREATE TABLE IF NOT EXISTS groups("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,"
        "active TINYINT DEFAULT 1,"
        "poll_at TIME NOT NULL,"
        "tg_id INT NOT NULL"
        ")"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS polls("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,"
        "open TINYINT NOT NULL DEFAULT 1,"
        "tg_id INT NOT NULL,"
        "group_id INTEGER NOT NULL,"
        "FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE"
        ")"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS answers("
        "id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,"
        "username VARCHAR(64),"
        "user VARCHAR(64),"
        "mood INT NOT NULL,"
        "poll_id INTEGER NOT NULL,"
        "FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE"
        ")"
    )

    return db


database = init_database()


def stop_daily_poll(app: Application, chat_id: int) -> None:
    for job in app.job_queue.get_jobs_by_name(f"daily-poll-{chat_id}"):
        job.job.remove()


def schedule_daily_poll(app: Application, chat_id: int, at: datetime.datetime) -> None:
    app.job_queue.run_daily(
        daily_poll,
        name=f"daily-poll-{chat_id}",
        time=datetime.time(at.hour, at.minute, tzinfo=pytz.timezone("cet")),
        chat_id=chat_id,
    )


def sync_group_polls(app: Application) -> None:
    groups = database.execute("SELECT tg_id, poll_at FROM groups WHERE active=1").fetchall()
    for group in groups:
        stop_daily_poll(app, group[0])
        schedule_daily_poll(app, group[0], datetime.datetime.strptime(group[1], "%Y-%d-%m %H:%M:%S"))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    time_str = update.effective_message.text.replace(f"/{COMMAND}", "").strip(" ")
    if time_str == "":
        await update.effective_message.reply_text(f"Usage: /{COMMAND} H:M")
        return

    try:
        poll_at = datetime.datetime.strptime(time_str, '%H:%M')
    except ValueError:
        await update.effective_message.reply_text(f"invalid time '{time_str}'. "
                                                  f"Please provide a valid start time."
                                                  f"Usage: /{COMMAND} H:M")
        return

    res = database.execute("SELECT id FROM groups WHERE tg_id=?", (chat.id,)).fetchone()
    if res is not None:
        database.execute("UPDATE groups SET poll_at=? WHERE id=?", (str(poll_at), res[0]))
        stop_daily_poll(context.application, chat.id)
    else:
        database.execute("INSERT INTO groups (tg_id, poll_at) VALUES (?, ?)", (str(chat.id), str(poll_at)))
    database.commit()
    schedule_daily_poll(context.application, chat.id, poll_at)

    await update.effective_message.reply_text(MESSAGES["registered"].replace("{time}", time_str))


async def daily_poll(context: CallbackContext):
    message = await context.bot.send_poll(
        chat_id=context.job.chat_id,
        question=MESSAGES["question"],
        options=mood_options(),
        is_anonymous=False,
        correct_option_id=False,
    )
    database.execute(
        "INSERT INTO polls (tg_id, group_id) VALUES (?, ?)",
        (message.poll.id, context.job.chat_id)
    )
    database.commit()
    context.application.job_queue.run_once(
        close_poll,
        when=datetime.time(23, 59, 59, tzinfo=pytz.timezone("cet")),
        data={"message": message}
    )


async def close_poll(context: CallbackContext):
    message = context.job.data["message"]
    poll = await context.bot.stop_poll(message_id=message.id, chat_id=message.chat_id)

    database.execute(
        "UPDATE polls SET open=0 WHERE tg_id=?",
        (poll.id,)
    )
    database.commit()

    answers = database.execute(
        "SELECT mood, user FROM answers "
        "INNER JOIN polls ON polls.id = answers.poll_id "
        "WHERE polls.tg_id = ?",
        (poll.id,)
    ).fetchall()

    highest, lowest = None, None
    for ans in answers:
        if (highest is None or ans[0] > highest[0]) and ans[0] >= 5:
            highest = ans
        elif (lowest is None or ans[0] < lowest[0]) and ans[0] < 5:
            lowest = ans

    print(highest, lowest)

    if highest is not None:
        text = await mood_message(highest[0], highest[1],[])
        await context.bot.send_message(message.chat_id, text=text)
    if lowest is not None:
        text = await mood_message(lowest[0], lowest[1], [])
        await context.bot.send_message(message.chat_id, text=text)


async def handle_answer(update: Update, _) -> None:
    answer = update.poll_answer
    poll = database.execute(
        "SELECT id FROM polls WHERE tg_id=?",
        (answer.poll_id,)
    ).fetchone()
    if poll is None:
        return

    mood = MOOD_ID_LOOKUP[answer.option_ids[0]]
    username = answer.user.username or "unknown"
    user = answer.user.full_name or "Unknown"

    database.execute(
        "INSERT INTO answers (username, user, mood, poll_id) VALUES (?, ?, ?, ?)",
        (username, user, mood, poll[0])
    )
    database.commit()


def main() -> None:
    application = Application.builder().token(os.environ.get('BOT_TOKEN')).build()
    sync_group_polls(application)

    application.add_handler(CommandHandler(COMMAND, start))
    application.add_handler(PollAnswerHandler(handle_answer))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
