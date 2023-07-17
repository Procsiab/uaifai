#!/usr/bin/env python3

import asyncio
from freebox_api import Freepybox, exceptions as fbx_except

import os
import platform
import sys

from wonderwords import RandomWord
import string
import random
import pyqrcode


ROUTER_HOSTNAME = 'myiliadbox.iliad.it'  # for Italian Iliadbox
# ROUTER_HOSTNAME = 'mafreebox.freebox.fr'  # for French Freebox
API_VERSION = 'v10'
APP_ID = 'net.procsiab.uaifai'
APP_NAME = 'Uai-Fai'
APP_VERSION = '0.0.1'
SAVE_FILE_PATH = 'uaifai_authz.json'


def get_hostname() -> str:
    if platform.system() == "Windows":
        return platform.uname().node
    else:
        return os.uname()[1]


def create_random_apname() -> str:
    randword = RandomWord()
    name = randword.word(include_parts_of_speech=['nouns'], word_min_length=5, word_max_length=10) \
        + '_' + randword.word(include_parts_of_speech=['adjectives'], word_min_length=5, word_max_length=10)
    return name


def create_random_key() -> str:
    length = 30
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    key = ''.join(random.choice(chars) for i in range(0, length))
    return key


def should_print_qr() -> bool:
    if '-noqr' in sys.argv:
        return False
    else:
        return True


def get_apname_arg() -> str:
    try:
        if '-apname' in sys.argv:
            return str(sys.argv[sys.argv.index('-apname') + 1])
        else:
            return None
    except Exception:
        print('⛔ Error in reading the AP name argument')
        return None


def get_duration_arg() -> int:
    try:
        if '-duration' in sys.argv:
            return int(sys.argv[sys.argv.index('-duration') + 1])
        else:
            return -1
    except Exception:
        print('⛔ Error in reading the duration in seconds argument')
        return -1


def get_numusers_arg() -> int:
    try:
        if '-numusers' in sys.argv:
            return int(sys.argv[sys.argv.index('-numusers') + 1])
        else:
            return -1
    except Exception:
        print('⛔ Error in reading the users number argument')
        return -1


def print_help() -> None:
    if '-help' in sys.argv:
        print('🔎 Usage: python main.py [-help] [-noqr] [-apname <custom_name>] [-duration <seconds>] [-numusers <number>]')
        print('   -noqr: will not print the QR-code to the terminal')
        print('   -apname <custom_name>: set the name of the guest password to custom_name')
        print('   -duration <seconds>: set the number of seconds before expiring the guest key')
        print('   -numusers <number>: set the number of concurrent users allowed to share the same guest key')
        exit(0)


async def main():
    global API_VERSION
    global APP_ID
    global APP_NAME
    global APP_VERSION
    global SAVE_FILE_PATH

    # If requested with an argument, print help and exit
    print_help()

    # Prepare the connector instance
    app_meta_dict = {
        'app_id': APP_ID,
        'app_name': APP_NAME,
        'app_version': APP_VERSION,
        'device_name': get_hostname(),
    }
    fbx = Freepybox(app_desc=app_meta_dict, token_file=SAVE_FILE_PATH, api_version=API_VERSION)

    # Test the API and authorize this application
    print('   Test the API connection to the router')
    if not os.path.exists(SAVE_FILE_PATH):
        print('👆 Click the right arrow on the router to authorize...')
    try:
        await fbx.open(host=ROUTER_HOSTNAME, port=443)
        print('✅ Iliadbox API version: ' + fbx.api_version)
    except Exception as e:
        print('⛔ Unable to connect to the router')
        print('   Message: ' + e)
        await fbx.close()
        return 1

    # Run the code to create a guest custom key
    if get_apname_arg() is not None:
        guest_ap_name = get_apname_arg()
    else:
        guest_ap_name = create_random_apname()
    if get_duration_arg() >= 0:
        guest_ap_duration = get_duration_arg()
    else:
        guest_ap_duration = 86400
    if get_numusers_arg() >= 0:
        guest_ap_users = get_numusers_arg()
    else:
        guest_ap_users = 1
    guest_ap_password = create_random_key()
    guest_ap_request_data = {
        'description':   guest_ap_name,
        'key':           guest_ap_password,
        'max_use_count': str(guest_ap_users),
        'duration':      guest_ap_duration,
        'access_type':   'net_only',
    }
    try:
        await fbx.wifi.create_wifi_custom_key(guest_ap_request_data)
        print('✅ Created guest AP: ' + guest_ap_name)
        print('   Password: ' + guest_ap_password)
    except fbx_except.InsufficientPermissionsError:
        print('🔧 You should check from the router\'s settings that your token has the "edit settings" permission')
        await fbx.close()
        return 0
    except fbx_except.AuthorizationError:
        print('🔧 The saved token appears to be revoked: you may want to delete the "uaifai_authz.json" and authorize a new token')
        return 1
    except Exception as e:
        print('⛔ Error in creating guest AP')
        print('   Message: ' + str(e))
        await fbx.close()
        return 1

    # Print the QR code for connecting
    if should_print_qr():
        try:
            ssid_request = await fbx.wifi.get_bss()
            base_ap_name = ssid_request[0]['bss_params']['ssid']
        except Exception:
            print('⛔ Error in reading the default SSID')
            print('   Message: ' + ssid_request['msg'])
            return 1
        qr_wifi_ap_string = 'WIFI:T:WPA;S:' + base_ap_name + ';P:' + guest_ap_password + ';;'
        printable_qr_string = pyqrcode.create(qr_wifi_ap_string)
        print(printable_qr_string.terminal())

    # Invalidate the session token
    try:
        await fbx.close()
        print('✅ Successful session logout')
    except Exception:
        print('⛔ Error in logging out')
        print('   Message: ' + ssid_request['msg'])
        return 1


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
