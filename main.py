#!/usr/bin/env python3

import json
import requests
import os
import platform

from binascii import hexlify
import hmac
import hashlib

from wonderwords import RandomWord
import string
import random
import pyqrcode


ROUTER_IP = '192.168.1.254'
API_BASE_URL = 'http://' + ROUTER_IP
API_VERSION = 'v0'
LOCAL_HOSTNAME = 'local'
APP_ID = 'net.procsiab.uaifai'
APP_NAME = 'Uai-Fai'
APP_VERSION = '0.0.1'
SAVE_FILE_PATH = 'uaifai_authz.json'

AUTHORIZATION_SINGLETON = {
    'app_token': '',
    'track_id': '',
    'challenge': '',
}


def get_hostname() -> str:
    if platform.system() == "Windows":
        return(platform.uname().node)
    else:
        return(os.uname()[1])


def new_challenge(track_id: str) -> dict:
    _api_uri = API_BASE_URL + '/api/' + API_VERSION + '/login/authorize/' + track_id
    return requests.get(_api_uri).json()


def new_session() -> dict:
    _api_uri = API_BASE_URL + '/api/' + API_VERSION + '/login/'
    return requests.get(_api_uri).json()


def update_challenge(new_challenge: str) -> None:
    AUTHORIZATION_SINGLETON['challenge'] = new_challenge


def update_trackid(new_trackid: str) -> None:
    AUTHORIZATION_SINGLETON['track_id'] = new_trackid


def update_apptoken(new_apptoken: str) -> None:
    AUTHORIZATION_SINGLETON['app_token'] = new_apptoken


def get_challenge() -> str:
    return AUTHORIZATION_SINGLETON['challenge']


def get_trackid() -> str:
    return AUTHORIZATION_SINGLETON['track_id']


def get_apptoken() -> str:
    return AUTHORIZATION_SINGLETON['app_token']


def create_session_password(app_token: str, challenge: str) -> str:
    digester = hmac.new(bytes(app_token, 'UTF-8'),
                        bytes(challenge, 'UTF-8'), hashlib.sha1)
    signature_digest = digester.digest()
    signature_encode = hexlify(signature_digest).decode('ascii')
    return signature_encode


def create_random_apname() -> str:
    randword = RandomWord()
    name = 'guest-' + randword.word(include_parts_of_speech=['nouns'], word_min_length=5, word_max_length=10) \
                    + '_' + randword.word(include_parts_of_speech=['adjectives'], word_min_length=5, word_max_length=10)
    return name


def create_random_key() -> str:
    length = 30
    chars = string.ascii_lowercase + string.ascii_uppercase + string.digits
    key = ''.join(random.choice(chars) for i in range(0, length))
    return key


def main():
    global ROUTER_IP
    global API_BASE_URL
    global API_VERSION
    global LOCAL_HOSTNAME
    global APP_ID
    global APP_NAME
    global APP_VERSION
    global SAVE_FILE_PATH
    global AUTHORIZATION_SINGLETON

    print('Test the API connection to the router...')
    try:
        api_test_response = requests.get(API_BASE_URL + '/api_version').json()
        API_VERSION = 'v' + api_test_response['api_version'].split('.')[0]
        print('✅ Iliadbox API version: ' + API_VERSION)
    except Exception:
        print('⛔ Unable to connect to the router at: ' + ROUTER_IP)
        return 1

    if not os.path.exists(SAVE_FILE_PATH):
        app_auth_token_data = {
            'app_id':      APP_ID,
            'app_name':    APP_NAME,
            'app_version': APP_VERSION,
            'device_name': get_hostname(),
        }
        try:
            app_auth_challenge = requests.post(API_BASE_URL + '/api/' + API_VERSION + '/login/authorize/',
                                               json.dumps(app_auth_token_data)).json()
            print('👆 Click the right arrow on the Iliadbox to authorize...')

            app_auth_track_id = str(app_auth_challenge['result']['track_id'])
            app_auth_status = new_challenge(app_auth_track_id)
            while app_auth_status['result']['status'] == 'pending':
                app_auth_status = new_challenge(app_auth_track_id)
            print('✅ Authorization successful!')
        except Exception:
            print('⛔ Error in authorizing this application')
            print('   Message' + app_auth_status['msg'])
            return 1

        update_apptoken(app_auth_challenge['result']['app_token'])
        update_trackid(app_auth_track_id)
        update_challenge(app_auth_status['result']['challenge'])
        try:
            with open(SAVE_FILE_PATH, 'w') as savefile:
                json.dump(AUTHORIZATION_SINGLETON, savefile)
            print('💾 Saved credentials to file: ' + SAVE_FILE_PATH)
        except Exception:
            print('⛔ Error in saving credentials to file: ' + SAVE_FILE_PATH)
            return 1
    else:
        with open(SAVE_FILE_PATH, 'r') as savefile:
            saved_credentials = json.load(savefile)
            update_apptoken(saved_credentials['app_token'])
            update_trackid(saved_credentials['track_id'])
            update_challenge(saved_credentials['challenge'])
        print('💾 Loaded credentials from file: ' + SAVE_FILE_PATH)

    # Update the challenge value just in case it has rotated
    current_challenge = new_session()
    update_challenge(current_challenge['result']['challenge'])
    session_password = create_session_password(get_apptoken(), get_challenge())
    app_id_password_data = {
        'app_id': APP_ID,
        'app_version': APP_VERSION,
        'password': session_password,
    }
    try:
        session_open_request = requests.post(API_BASE_URL + '/api/' + API_VERSION + '/login/session/',
                                             json.dumps(app_id_password_data)).json()
        if not session_open_request['success']:
            raise Exception
        session_token = session_open_request['result']['session_token']
        print('✅ Opened app session: ' + APP_ID)
    except Exception:
        print('⛔ Error in opening session')
        print('   Message: ' + session_open_request['msg'])
        return 1

    # Run the code to create a guest AP / custom key
    guest_ap_name = create_random_apname()
    guest_ap_password = create_random_key()
    guest_ap_request_data = {
        'description':   guest_ap_name,
        'key':           guest_ap_password,
        'max_use_count': '2',
        'duration':      86400,
        'access_type':   'net_only',
    }
    session_auth_header = {'X-Fbx-App-Auth': session_token}
    try:
        guest_ap_request = requests.post(API_BASE_URL + '/api/' + API_VERSION + '/wifi/custom_key/',
                                         json.dumps(guest_ap_request_data),
                                         headers=session_auth_header).json()
        if not guest_ap_request['success']:
            raise Exception
        print('✅ Created guest AP: ' + guest_ap_name)
        print('   Password: ' + guest_ap_password)
    except Exception:
        print('⛔ Error in creating guest AP')
        print('   Message: ' + guest_ap_request['msg'])
        return 1

    # Print the QR code for connecting
    try:
        ssid_request = requests.get(API_BASE_URL + '/api/' + API_VERSION + '/wifi/bss/',
                                         headers=session_auth_header).json()
        base_ap_name = ssid_request['result'][1]['bss_params']['ssid']
    except Exception:
        print('⛔ Error in reading the default SSID')
        print('   Message: ' + guest_ap_request['msg'])
        return 1
    qr_wifi_ap_string = 'WIFI:T:WPA;S:' + base_ap_name + ';P:' + guest_ap_password + ';;'
    printable_qr_string = pyqrcode.create(qr_wifi_ap_string)
    print(printable_qr_string.terminal())


if __name__ == "__main__":
    main()
