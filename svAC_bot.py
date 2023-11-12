import discord, re, random, time, asyncio, traceback
from discord.ext import commands
from assaultcube_server_reader import get_server_info_and_namelist, get_playerstats
from config import SV_TOKEN, SV_CHANNEL_ID, server_ip, server_port, mastermode_emojis, gamemode_names

last_message_id = None
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

def create_team_rows(players, gamemode, show_stats=True):
    table_rows = []
    for player in players:
        player_name = player["name"][:15].ljust(15)

        if show_stats:
            player_frags = str(player["frags"]).center(5)
            player_deaths = str(player["deaths"]).center(6)
            player_teamkills = str(player["teamkills"]).center(3)
            player_accuracy = f"{player['accuracy']:.0f}%".center(3)
            player_damage = str(player["damage"]).center(8)

            row = f"{player_name} {player_frags} {player_deaths} {player_teamkills} {player_accuracy} {player_damage}"

            if "flag" in gamemode.lower():
                player_flags = str(player["flags"]).rjust(4)
                row = f"{player_name} {player_flags} {player_frags} {player_deaths} {player_teamkills} {player_accuracy} {player_damage}"

            table_rows.append(row)
        else:
            table_rows.append(player_name)

    return "```\n" + "\n".join(table_rows) + "```"

def create_server_embed(server_info, ip, port, player_stats):
    title = clean_description(server_info["server_description"])
    mastermode_emoji = mastermode_emojis[server_info["mastermode"]]
    gamemode = gamemode_names[server_info["gamemode"]]
    gamemode_lower = gamemode.lower()
    map_name = server_info["server_map"]
    minutes_remaining = server_info["minutes_remaining"]
    online_players = f"{server_info['nb_connected_clients']}/{server_info['max_client']}"
    connect_info = f"/connect {ip} {port - 1}"

    cla_players = [player for player in player_stats if player["team"] == "CLA"]
    rvsf_players = [player for player in player_stats if player["team"] == "RVSF"]

    cla_flags = sum(player["flags"] for player in cla_players)
    cla_frags = sum(player["frags"] for player in cla_players)
    rvsf_flags = sum(player["flags"] for player in rvsf_players)
    rvsf_frags = sum(player["frags"] for player in rvsf_players)

    if cla_flags > rvsf_flags or (cla_flags == rvsf_flags and cla_frags > rvsf_frags):
        embed_color = 0xFF0000  # Red for CLA
    elif rvsf_flags > cla_flags or (cla_flags == rvsf_flags and rvsf_frags > cla_frags):
        embed_color = 0x0000FF  # Blue for RVSF
    else:
        embed_color = random.randint(0, 0xFFFFFF)

    embed = discord.Embed(
        title=f"{title} {mastermode_emoji} `{server_info['mastermode'].capitalize()}` {online_players} players online",
        description=f"**{gamemode}** on map **{map_name}**, **{minutes_remaining} minutes** remaining.\n\n{connect_info}",
        color=embed_color
    )

    if player_stats:
        header = "```name            frags deaths tks acc damage```"
        if "flag" in gamemode_lower:
            header = "```name            flags frags deaths tks acc damage```"

        cla_section = "```CLA```\n" + create_team_rows(cla_players, gamemode_lower)
        rvsf_section = "```RVSF```\n" + create_team_rows(rvsf_players, gamemode_lower)

        team_score = f"**CLA {cla_frags}** vs **RVSF {rvsf_frags}**"
        if "flag" in gamemode_lower:
            team_score = f"**CLA {cla_flags} ({cla_frags})** vs **RVSF {rvsf_flags} ({rvsf_frags})**"
        embed.add_field(name="Team Score", value=team_score, inline=False)

        player_stats_table = header + "\n\n" + cla_section + "\n\n" + rvsf_section

        spect_players = [player for player in player_stats if player["team"] == "SPECT"]
        if spect_players:
            spect_section = "```SPECT```\n" + create_team_rows(spect_players, gamemode_lower, show_stats=False)
            player_stats_table += "\n\n" + spect_section

        embed.add_field(name="Player Statistics", value=player_stats_table, inline=False)

    embed.set_thumbnail(url="https://avatars.githubusercontent.com/u/5957666?s=200&v=4")

    return embed

def clean_description(description):
    return re.sub(r'\f[0-9A-Z]', '', description)

@bot.event
async def on_ready():
    print(f'{bot.user.name} Successfully connected to Discord!')
    print(f"Target channel: {SV_CHANNEL_ID}")
    bot.loop.create_task(send_info())

async def send_info():
    global last_message_id
    while True:
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        print(f"[{current_time}] Sending information from the server to the channel {SV_CHANNEL_ID}")
        channel = bot.get_channel(SV_CHANNEL_ID)
        server_info = get_server_info_and_namelist(server_ip, server_port)

        if server_info:
            player_stats = get_playerstats(server_ip, server_port)
            embed = create_server_embed(server_info, server_ip, server_port, player_stats)
            try:
                if last_message_id:
                    try:
                        last_message = await channel.fetch_message(last_message_id)
                        await last_message.edit(embed=embed)
                        print(f"Message updated successfully: {last_message_id}")
                    except discord.errors.NotFound:
                        last_message = await channel.send(embed=embed)
                        last_message_id = last_message.id
                        print(f"Message sent successfully: {last_message_id}")
                    except Exception as e:
                        print(f"Error updating message: {e}")
                        traceback.print_exc()
                else:
                    last_message = await channel.send(embed=embed)
                    last_message_id = last_message.id
                    print(f"Message sent successfully: {last_message_id}")
            except Exception as e:
                print(f"Error sending/updating message: {e}")
                traceback.print_exc()
        else:
            print(f"Server not found at {server_ip}:{server_port}")

        await asyncio.sleep(60)

bot.run(SV_TOKEN)