"""
Helper module to get data from an assault cube server
"""
import socket
import struct

EXTPING_NOP = b"\x01\x00"
EXTPING_NAMELIST = b"\x01\x01"
EXTPING_SERVERINFO = b"\x01\x02"
EXTPING_MAPROT = b"\x01\x03"
EXTPING_UPLINKSTATS = b"\x01\x04"
EXTPING_NUM = b"\x01\x05"
EXT_UPTIME = b"\x00\x00"
EXT_PLAYERSTATS = b"\x00\x01"
EXT_TEAMSCORE = b"\x00\x02"

def unpack_helper(fmt, data):
    """
    Unpack X element(s) of type(s) fmt from data
    return The X elements, the data without that element, the removed data
    https://stackoverflow.com/questions/3753589/
    Ex : unpack_helper("bb", b"\x01\x01")
    """
    size = struct.calcsize(fmt)
    return struct.unpack(fmt, data[:size]), data[size:], data[:size]

def getint(data):
    """
    Unpack 1 int (signed char) from data
    Return that int and the data
    See putint and getint in protocol.cpp
    """
    # Check if there is at least 1 byte in the buffer
    if len(data) < 1:
        return 0, data  # Can return a default value or handle differently
    
    my_int, data, _ = unpack_helper("b", data)
    
    # Check if the value is -128, indicating a 2-byte representation
    if my_int[0] == -128:
        # Check if there are at least 2 bytes in the buffer
        if len(data) < 2:
            return 0, data  # Can return a default value or handle differently
        
        # Try reading the value in 2 bytes (cf putint in protocol.cpp)
        my_int, data, _ = unpack_helper("H", data)
        
    return my_int[0], data

def getchar(data):
    """
    Unpack 1 char from data
    Return that char and the data
    """
    my_char, data, _ = unpack_helper("c", data)
    # We know we have only 1 int so only return first tuple value
    return my_char[0], data

def getstring(data):
    """
    Get the next string from data, end of string at \x00 or if no more data
    Return the string and the remaining data
    """
    #Strings ends with 0
    my_string = ""
    while True:
        if len(data) == 0:
            break
        char, data = getchar(data)
        if char == b"\x00":
            break
        my_string+=char.decode("utf-8")
    return my_string, data

def get_server_info_and_namelist(server_ip, port):
    """
    Query server info and connected player names from a server
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    server_socket.settimeout(3)
    server_socket.sendto(EXTPING_NAMELIST, (server_ip, port))
    data, _ = server_socket.recvfrom(4096)
    server_socket.close()
    _, data, _ = unpack_helper("bb", data) # extping_code don't store since it's unused
    _, data, _ = unpack_helper("bbb", data) # proto_version don't store since it's unused

    gamemode, data = getint(data)
    nb_connected_clients, data = getint(data)
    minutes_remaining, data = getint(data)
    server_map, data = getstring(data)
    server_description, data =  getstring(data)
    max_client, data = getint(data)

    mastermode, data, _ = unpack_helper("bb", data)

    # Convert mastermode value to "known" value
    if mastermode[0] == -128:
        mastermode, data, _ = unpack_helper("bb", data)
        mastermode = "MATCH"

    if mastermode in ((0, 1), (1, 1)):
        mastermode = "OPEN"
    elif mastermode in ((64, 1), (65, 1)):
        mastermode = "PRIVATE"

    playerlist = []
    while data != b"\x00": # Better check ?
        player, data = getstring(data)
        playerlist.append(player)
    return {
            "gamemode": gamemode,
            "mastermode": mastermode,
            "nb_connected_clients": nb_connected_clients,
            "minutes_remaining": minutes_remaining,
            "server_map": server_map,
            "server_description": server_description,
            "max_client": max_client,
            "playerlist": playerlist
    }

def read_player_data(player_data):
    """
    Read one player data (bytes format)
    Return a dictionnary with all read informations
    See extinfo_statsbuf function in server.cpp
    """
    # Should have more data than this
    # Sometime the server send incomplete data
    # TODO: Add better check
    if len(player_data) < 20:
        print(f"read_player_data Debug : {player_data}")
        return {}

    # extping_code don't store since it's unused
    _, player_data, _ = unpack_helper("bb", player_data)
    # proto_version don't store since it's unused
    _, player_data, _ = unpack_helper("bbb", player_data)
    # EXT_PLAYERSTATS_RESP_STATS (Should = -11) Maybe I should make a check
    _, player_data, _ = unpack_helper("bb", player_data)

    client_number, player_data = getint(player_data)
    ping, player_data = getint(player_data)
    name, player_data = getstring(player_data)
    print(f"name {name}")
    team, player_data = getstring(player_data)
    frags, player_data = getint(player_data)
    flags, player_data = getint(player_data)
    deaths, player_data = getint(player_data)
    teamkills, player_data = getint(player_data)
    accuracy, player_data = getint(player_data) # Not correct with sniper headshots ?
    health, player_data = getint(player_data)
    armour, player_data = getint(player_data)
    gun, player_data = getint(player_data) # 5 = sniper
    role, player_data = getint(player_data)
    state, player_data = getint(player_data) # (Alive,Dead,Spawning,Lagged,Editing)

    ip_tuple, player_data, _ = unpack_helper("BBB", player_data)
    ip = ".".join(str(byte) for byte in ip_tuple) + ".0"

    damage = -1
    damage, player_data, = getint(player_data)

    # Total potential damages, it increses even if you don't hit
    shotdamage = -1
    shotdamage, player_data, = getint(player_data)
    
    return {
        "client_number": client_number,
        "ping": ping,
        "name": name,
        "team": team,
        "frags": frags,
        "flags": flags,
        "deaths": deaths,
        "teamkills": teamkills,
        "accuracy": accuracy,
        "health": health,
        "armour": armour,
        "gun": gun,
        "role": role,
        "state": state,
        "ip": ip,
        "damage": damage,

    }

def get_playerstats(server_ip, port):
    """
    Query server for player stats
    Return all players stats as dict
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, 0)
    server_socket.settimeout(3)
    # We could also query 1 player stat using : client_number = bytes([2]) # for client_number 2
    client_number = b"\xff" # Send -1 to have all player stats
    data_to_send = EXT_PLAYERSTATS + client_number
    server_socket.sendto(data_to_send, (server_ip, port))
    # The query will return multiple packets
    # The first one will contain the client_number of connected players
    # Then for each connected players we will receive his stats
    data_client_number, _ = server_socket.recvfrom(4096)
    # extping_code don't store since it's unused
    _, data_client_number, _ = unpack_helper("bb", data_client_number)
    # proto_version don't store since it's unused
    _, data_client_number, _ = unpack_helper("bbb", data_client_number)
    # EXT_PLAYERSTATS_RESP_IDS (Should = -10)
    ext_playerstats_resp_ids, data_client_number, _ = unpack_helper("bb", data_client_number)
    if ext_playerstats_resp_ids[1] != -10:
        print(f"get_playerstats Debug: {ext_playerstats_resp_ids} {data_client_number}")
    client_number_list = []
    while data_client_number:
        client_number, data_client_number = getint(data_client_number)
        client_number_list.append(client_number)
    players_stats = []
    # Here we know how many client_number we have so we can receive our data
    for client_number in client_number_list:
        player_data = server_socket.recv(65535)
        dict_player_data = read_player_data(player_data)
        # Sometime the server sends bad data
        if "name" in dict_player_data and dict_player_data["name"] != "":
            players_stats.append(dict_player_data)

    server_socket.close()
    return players_stats
