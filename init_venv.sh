#! /usr/bin/env bash

rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp freebox_certificates.pem $(find .venv -name 'freebox_certificates.pem')
