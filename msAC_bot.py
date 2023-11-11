import os
import requests
import discord
import re
import time
import asyncio
import traceback
import hashlib
from discord.ext import commands
from assaultcube_server_reader import get_server_info_and_namelist
from datetime import datetime, timedelta
from config import TOKEN, CHANNEL_ID
import json

last_message_id = None
last_servers_update = None
cached_server_list = []

mastermode_emojis = {
    "OPEN": ":dove:",
    "PRIVATE": ":closed_lock_with_key:",
    "MATCH": ":lock:",
}

gamemode_names = {
    0: "Team deathmatch",
    1: "Co-operative editing",
    2: "Deathmatch",
    3: "Survivor",
    4: "Team survivor",
    5: "Capture the flag",
    6: "Pistol frenzy",
    7: "Bot team deathmatch",
    8: "Bot deathmatch",
    9: "Last swiss standing",
    10: "One shot, one kill",
    11: "Team one shot, one kill",
    12: "Bot one shot, one kill",
    13: "Hunt the flag",
    14: "Team keep the flag",
    15: "Keep the flag",
    16: "Team pistol frenzy",
    17: "Team last swiss standing",
    18: "Bot pistol frenzy",
    19: "Bot last swiss standing",
    20: "Bot team survivor",
    21: "Bot team one shot",
}

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

#Generate a color based on the IP and port.
def get_color_from_ip_port(ip, port):
    unique_identifier = f"{ip}:{port}"
    md5_hash = hashlib.md5(unique_identifier.encode()).hexdigest()
    color = int(md5_hash[:6], 16)
    return color

#Create an embed message for a server.
def create_server_embed(server_info, ip, port, color):
    title = clean_description(server_info["server_description"])
    mastermode_emoji = mastermode_emojis[server_info["mastermode"]]
    gamemode = gamemode_names[server_info["gamemode"]]
    map_name = server_info["server_map"]
    minutes_remaining = "∞" if gamemode == "Co-operative editing" else server_info["minutes_remaining"]
    online_players = f"{server_info['nb_connected_clients']}/{server_info['max_client']}"
    connect_info = f"/connect {ip} {port - 1}"

    embed = discord.Embed(
        title=f"{title} {mastermode_emoji} `{server_info['mastermode'].capitalize()}` {online_players} players online",
        description=f"**{gamemode}** on map **{map_name}**, **{minutes_remaining} minutes** remaining.\n\n{connect_info}",
        color=color
    )

    embed.set_thumbnail(url="https://avatars.githubusercontent.com/u/5957666?s=200&v=4")
    return embed

#Retrieve the list of servers from the master server.
def get_all_servers():
    global last_servers_update, cached_server_list

    if last_servers_update and datetime.now() - last_servers_update < timedelta(hours=12):
        return cached_server_list

    try:
        response = requests.get("http://ms.cubers.net/retrieve.do?action=list&name=none")
        if response.status_code == 200:
            servers = response.text.splitlines()
            new_server_list = [(server.split()[1], int(server.split()[2]) + 1) for server in servers if server.startswith("addserver")]

            with open("ServerListMasterServer.json", "w") as file:
                json.dump(new_server_list, file)

            cached_server_list = new_server_list
            last_servers_update = datetime.now()
    except requests.RequestException:
        pass

    if os.path.exists("ServerListMasterServer.json"):
        with open("ServerListMasterServer.json", "r") as file:
            cached_server_list = json.load(file)

    return cached_server_list

#Clean up server description.
def clean_description(description):
    return re.sub(r'\f[0-9A-Z]', '', description)

#Event handler when the bot is ready.
@bot.event
async def on_ready():
    print(f'{bot.user.name} successfully connected to Discord!')
    print(f"target channel: {CHANNEL_ID}")
    bot.loop.create_task(send_info())

#Periodically send server information to the specified channel.
async def send_info():
    global last_message_id
    while True:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        print(f"[{current_time}] Sending information from the server to the channel {CHANNEL_ID}")
        channel = bot.get_channel(CHANNEL_ID)

        all_servers = get_all_servers()
        embeds = []

        for ip, port in all_servers:
            print(f"Checking server {ip}:{port}")
            try:
                server_info = get_server_info_and_namelist(ip, port)
                if server_info["nb_connected_clients"] > 0:
                    color = get_color_from_ip_port(ip, port)
                    embed = create_server_embed(server_info, ip, port, color)
                    embeds.append(embed)
            except TimeoutError:
                print(f"TimeoutError: Server {ip}:{port} did not respond.")
                continue
            except Exception as e:
                print(f"Unexpected error while processing server {ip}:{port}: {e}")
                continue

        try:
            if last_message_id:
                try:
                    last_message = await channel.fetch_message(last_message_id)
                    await last_message.edit(embeds=embeds)
                    print(f"Message updated successfully: {last_message_id}")
                except discord.errors.NotFound:
                    last_message = await channel.send(embeds=embeds)
                    last_message_id = last_message.id
                    print(f"Message sent successfully: {last_message_id}")
            else:
                last_message = await channel.send(embeds=embeds)
                last_message_id = last_message.id
                print(f"Message sent successfully: {last_message_id}")
        except Exception as e:
            print(f"Error sending/updating message: {e}")
            traceback.print_exc()

        await asyncio.sleep(60)

bot.run(TOKEN)