#!/usr/bin/env python

import sys
import yaml
import os
import argparse
import time
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning  # suppressing 'Unverified HTTPS request' msg
import json

from colorama import Fore, Back, Style

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)       # suppressing 'Unverified HTTPS request' msg

def get_url(conf):
  if 'dev' in conf['api']:
    base_url='http://localhost:8086/v2.0/projects/'
  else:
    base_url='https://api.localizejs.com/v2.0/projects/'

  return base_url+conf['api']['project']+'/resources'

def config():
  project = raw_input('Localize project key [None]: ')
  token = raw_input('Localize API token [None]: ')

  data = dict(
    api = dict(
      project = project,
      token = token
    ),
    push = dict(
      sources = [dict(file = '/full/path/to/your/file.language.format')]
    ),
    pull = dict(
      targets = [dict(file = '/full/path/to/your/file.language.format')]
    )
  )

  from os.path import expanduser
  home = expanduser("~")
  config_file = home + '/.localize/config.yml'

  if not os.path.exists(os.path.dirname(config_file)):
    try:
      os.makedirs(os.path.dirname(config_file))
    except OSError as exc: # Guard against race condition
      if exc.errno != errno.EEXIST:
        raise
  with open(config_file, 'w+') as out:
    out.write(yaml.dump(data, default_flow_style=False))

def push(conf):
  errors = []
  for source in conf['push']['sources']:
    url = get_url(conf)
    headers={ 'Authorization': 'Bearer ' + conf['api']['token'] }

    # Try and open the file
    try:
      file = open(source['file'], 'rb')
    except (IOError, OSError) as e:
      errors.append('Error: ' + str(e))
      break;

    content={ 'content': file }

    # Use the file extension to guess the language and format
    base = os.path.basename(source['file'])
    language, format = check_and_return_lang_format(base, 'push')     # refactoring, extracting duplicate code into method
    data={
      'language': language,
      'format': format.replace('yml','yaml').upper()  # replacing 'yml' file format to 'yaml'
    }

    r = requests.post(url, headers=headers, verify=False, data=data, files=content)

    if r.status_code != 200:
      message = 'Something went wrong. Please contact support.'
      res = json.loads(r.text)

      if res['meta']['error']['message']:
        message = res['meta']['error']['message'] + ' for file ' + source['file']

      errors.append(message)

  # If there are any errors display them to the user
  if errors:
    for error in errors:
      print(Fore.RED+error+Style.RESET_ALL)
  else:
    sys.exit(Fore.GREEN + 'Successfully pushed ' + str(len(conf['push']['sources'])) + ' file(s) to Localize!' + Style.RESET_ALL)

def pull(conf):
  errors = []

  if not 'targets' in conf['pull']:
    sys.exit(Fore.RED + 'Could not find any targets to pull. Please make sure your configuration is formed correctly.' + Style.RESET_ALL)

  for target in conf['pull']['targets']:
    if not target:
      sys.exit(Fore.RED + 'Could not find target.' + Style.RESET_ALL)

    url = get_url(conf)
    headers={
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + conf['api']['token'] 
    }

    # Use the file extension to guess the language and format
    base=os.path.basename(target['file'])
    language, format = check_and_return_lang_format(base, 'pull')        # refactoring, extracting duplicate code into method
    data={
      'language': language,
      'format': format.replace('yml','yaml').upper(),    # replacing 'yml' file format to 'yaml
      'filter': 'has-active-translations'
    }

    r = requests.get(url, headers=headers, verify=False, params=data, stream=True)

    if r.status_code != 200:
      message = 'Something went wrong. Please contact support.'
      res = json.loads(r.text)
      if res['meta']['error']['message']:
        message = res['meta']['error']['message'] + ' for file ' + target['file']

      errors.append(message)
    else:
      # Swap put the content of the file with the data
      with open(target['file'], 'wb') as file:
        for chunk in r.iter_content(chunk_size=1024): 
          if chunk: # filter out keep-alive new chunks
            file.write(chunk)

  # If there are any errors display them to the user
  if errors:
    for error in errors:
      print(Fore.RED + error + Style.RESET_ALL)
  else:
    sys.exit(Fore.GREEN + 'Successfully pulled ' + str(len(conf['pull']['targets'])) + ' file(s) to Localize!' + Style.RESET_ALL)

def check_and_return_lang_format(filename, type):
  if filename.count('.') != 2:                      # checking filename, shoud be '<name>.<lang>.<format>', for example project_name.ru.json
    sys.exit(Fore.RED + "Wrong filename for '" + type + "' type, target file have to has the following file format '<name>.<language>.<format>', for example project_name.ru.json" + Style.RESET_ALL)
  splitted_filename = filename.split('.')           # splitting filename by dot
  return splitted_filename[1],splitted_filename[2]  # returning language and format
