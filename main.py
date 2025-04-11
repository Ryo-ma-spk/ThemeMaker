import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction
from datetime import datetime, timedelta, timezone
import random
import config
from sheets.connector import reminder_sheet, theme_sheet
import os
from flask import Flask
import threading

# ======================
# 🤖 Bot本体の設定
# ======================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ======================
# 📅 /remind コマンド
# ======================
@tree.command(name="remind", description="指定日時にリマインダーを登録します")
@app_commands.describe(
    date="日時を YYYY/MM/DD HH:MM 形式で入力（例: 2025/04/01 10:00）",
    message="通知内容"
)
async def remind(interaction: Interaction, date: str, message: str):
    try:
        jst = timezone(timedelta(hours=9))
        dt = datetime.strptime(date, "%Y/%m/%d %H:%M").replace(tzinfo=jst)
        now = datetime.now(jst)

        if dt < now:
            await interaction.response.send_message(
                f"⚠️ 過去の日時（{dt.strftime('%Y-%m-%d %H:%M:%S')}）は登録できません！"
            )
            return

        formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
        channel_id = str(interaction.channel.id)

        try:
            reminder_sheet.append_row([formatted, message, channel_id, "FALSE"])
        except Exception as e:
            await interaction.response.send_message(f"❌ リマインダー登録中にエラー: {e}")
            return

        await interaction.response.send_message(
            f"✅ リマインダーを登録しました！\n📅 {formatted}\n📝 {message}"
        )

    except ValueError:
        await interaction.response.send_message(
            "❌ 日時の形式が正しくありません\n例: `2025/04/05 21:00`"
        )

# ======================
# 🎲 /theme コマンド
# ======================
@tree.command(name="theme", description="Google Sheetsからランダムなお題を生成します")
async def theme(interaction: Interaction):
    await interaction.response.send_message("お題を取得中...")

    try:
        rows = theme_sheet.get_all_values()
        columns = list(zip(*rows[1:]))

        a_column = [cell for cell in columns[0] if cell.strip()]
        b_column = [cell for cell in columns[1] if cell.strip()]
        c_column = [cell for cell in columns[2] if cell.strip()]

        random_a = random.choice(a_column)
        random_b = random.choice(b_column)
        random_c = random.choice(c_column)

        await interaction.followup.send(f"ランダムなお題：\n1: {random_a}\n2: {random_b}\n3: {random_c}")
    except Exception as e:
        await interaction.followup.send(f"❌ お題の取得に失敗しました: {e}")

# ======================
# ⏰ リマインダー通知機能
# ======================
@tasks.loop(minutes=1)
async def check_reminders():
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    print(f"🔄 リマインドチェック実行中（JST）: {now.strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        records = reminder_sheet.get_all_records()
        unsent_reminders = [
            (idx, row) for idx, row in enumerate(records, start=2)
            if row["is_sent"].strip().upper() != "TRUE"
        ]
    except Exception as e:
        print(f"❌ Google Sheets 読み込み失敗: {e}")
        return

    for idx, row in unsent_reminders:
        try:
            reminder_time = datetime.strptime(row["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=jst)
        except ValueError:
            print(f"⚠️ 無効な日付形式: {row['datetime']}")
            continue

        notify_time = reminder_time - timedelta(minutes=5)
        time_diff = (notify_time - now).total_seconds()

        if 0 <= time_diff <= 60:
            try:
                channel_id = int(row["channel_id"])
                channel = bot.get_channel(channel_id)

                if channel is None:
                    try:
                        channel = await bot.fetch_channel(channel_id)
                    except Exception:
                        print(f"❌ fetch_channel でもチャンネル取得失敗: {channel_id}")
                        continue

                formatted_jst = reminder_time.strftime("%Y-%m-%d %H:%M:%S")
                bot_name = bot.user.name
                await channel.send(
                    f"@everyone\n🔔 {bot_name}からのお知らせ！\n📝 {row['message']}（{formatted_jst}）"
                )
                reminder_sheet.update_cell(idx, 4, "TRUE")
            except Exception as e:
                print(f"❌ 通知中にエラー発生: {e}")

# ======================
# 🚀 Bot起動処理
# ======================
@bot.event
async def on_ready():
    print(f"✅ Bot is ready! Logged in as {bot.user}")
    try:
        await tree.sync()
        print("✅ Slash commands synced!")
        if not check_reminders.is_running():
            check_reminders.start()
            print("⏰ リマインダー通知ループを開始しました")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")

# ======================
# 🌐 Flask ルート (Koyeb対応)
# ======================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    try:
        app.run(host="0.0.0.0", port=8000)
    except Exception as e:
        print(f"❌ Flaskサーバー起動エラー: {e}")

# ======================
# ▶️ 実行
# ======================
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(os.environ.get("DISCORD_TOKEN", config.DISCORD_TOKEN))