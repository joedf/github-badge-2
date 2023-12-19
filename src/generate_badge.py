import os
import sys
import json
import requests
from pprint import pprint
from datetime import datetime, timedelta
from platform import python_version

from jinja2 import __version__ as jinja2_version
from jinja2 import Environment
from jinja2 import FileSystemLoader


# ensure script working dir
os.chdir(sys.path[0])


# code from GitHub\github-badge\app\customfilters.py
# ==============================================================

import re
from math import log

# Constants
QUANTAS = ('k', 'M', 'G', 'T', 'P')
EPOCH_STR = '1970-01-01T00:00:00Z'

def shortnum(value, precision=3):
	value = float(value)
	if value >= 1000:
		order = int(log(value, 1000))
		mult = 10 ** (order * 3)
		num = value / mult
		quanta = QUANTAS[order - 1]
	else:
		num = value
		quanta = ''
	fmt = "%%.%dg%%s" % precision
	return fmt % (num, quanta)


def smarttruncate(value, length=80, suffix='...', pattern=r'\w+'):
	value_length = len(value)
	if value_length > length:
		last_span = (0, value_length)
		for m in re.finditer(pattern, value):
			span = m.span()
			if span[1] > length:
				break
			else:
				last_span = span
		cutoff = last_span[1]
		if  cutoff > length:
			cutoff = length - len(suffix)
		return value[:cutoff] + suffix
	return value


# utility functions
# ==============================================================
def run_query(query): # A simple function to use requests.post to make the API call. Note the json= section.
	# modified from https://gist.github.com/gbaman/b3137e18c739e0cf98539bf4ec4366ad
	global GITHUB_API_KEY
	headers = {"Authorization": "Bearer "+GITHUB_API_KEY}
	request = requests.post('https://api.github.com/graphql', json={'query': query}, headers=headers)
	if request.status_code == 200:
		return request.json()
	else:
		raise Exception("Query failed to run by returning code of {}. {}".format(request.status_code, query))

def file2str(path):
	with open(path, 'r') as file:
		return file.read().strip()

def renderSaveAs(template_file,out_file,context):
	global G_j2_env
	template = G_j2_env.get_template(template_file)
	rendered_html = template.render(context)

	with open(out_file, "w", encoding='utf-8') as fp:
		fp.write(rendered_html)

	print('generated: '+out_file)

def nBound(value,minimum,maximum):
	# return a value within bounds
	return max(min(value,maximum),minimum)

def dtParseTimestamp(UTC_string):
	# parse timestamp strings like '1970-01-01T00:00:00Z'
	return datetime.strptime(UTC_string, '%Y-%m-%dT%H:%M:%SZ')

def gen_SparklineSVG(data):
	# generate a 7-day graph 20x14 pixels
	iw, ih = 20, 14

	# get max
	m = 1 # a minimum max of 1
	for day in data:
		m = max(m,day['count'])

	# generate svg
	svg = '<svg viewBox="0 0 {} {}" width="{}" height="{}"><g style="fill:SlateGray">\n'.format(iw,ih,iw,ih)
	for i in range(0,7):
		d = data[i]
		v = round( (d['count'] / m)*ih, 2 ) #scale val
		h = nBound(v,1,ih) #bound val
		x = i*3
		y = ih - h

		svg += '<rect width="2" height="{}" x="{}" y="{}"/>\n'.format(h,x,y)

	svg += '</g></svg>'

	return svg

def GitHubStats(rObj, ignore_repos=None):
	d = rObj['data']
	u = d['user']
	a = u['activity']

	# default latest commit search
	# has issue if app is used with automated commit or GitHub Actions
	# see the follow 'ignore_repos' code, for handling that case.
	try:
		lr = a['latestRepo'][0]['contributions']['repos'][0]['repository']
	except:
		lr = {}

	# get latest commits accouting for ignored repos, see following
	# https://github.com/joedf/github-badge-2/issues/4
	if ignore_repos is not None:
		latestCommits = []
		latestCommitsRepo = d['latestCommits']['repos']
		for repo in latestCommitsRepo:
			if repo['name'] not in ignore_repos:
				history = repo['defaultBranchRef']['target']['history']
				if history['totalCount'] > 0:
					lastCommit = history['nodes'][0]
					commitAuthor = lastCommit['author']['user']['login']
					if commitAuthor == u['login']:
						latestCommits.append({
							'repo': repo['name'],
							'message': lastCommit['message'],
							'commitUrl': lastCommit['commitUrl'],
							'date': lastCommit['committedDate']
						})
		
		if len(latestCommits) > 0:
			lastCommitDate = dtParseTimestamp(EPOCH_STR)
			for commit in latestCommits:
				# bogus old date to ignore error if date could not be parse, and push to bottom prio
				commitDate = dtParseTimestamp(commit.get('date', EPOCH_STR))
				if commitDate >= lastCommitDate:
					lr = {
						'name': commit['repo'],
						'url': commit['commitUrl'],
						'pushedAt': commit['date']
					}
		else:
			# Otherwise, we clear it since no recent commits were found with ignore_repos mode
			lr = {}


	# get stargarzers tally and top primary langs
	stargazers = 0
	topLangs = []

	for repo in u['sources']['repos']:
		# process any primary langs
		if (repo['primaryLanguage']) and len(repo['primaryLanguage']):
			lang = repo['primaryLanguage']['name']
			if lang not in topLangs:
				topLangs.append(lang)
		
		# add stargazers to sum
		stars = repo['stargazers']['totalCount']
		stargazers += stars


	# get latest (7 days) contributions / activity
	contribs = []

	for weeks in a['contributionCalendar']['weeks']:
		for days in weeks['contributionDays']:
			contribs.append({
				'count': days['contributionCount'],
				#'date': datetime.fromisoformat(days['date']) # python v3.8+
				'date': days['date']
			})

	# get recent max commits
	max_commits = 0
	for day in contribs:
		max_commits = max(day['count'], max_commits)

	# organize data
	retVal = {
		'login':             u['login'],
		'name':              u['name'],
		'followers':         u['followers']['totalCount'],
		'stargazers':        stargazers,
		'repos':             u['sources']['totalCount'],
		'forks':             d['forks']['repositoryCount'],
		'html_url':          u['url'],
		'avatar_url':        u['avatarUrl'],
		'languages':         topLangs,
		'last_project':      lr.get('name', False),
		'last_project_url':  lr.get('url'),
		'last_project_date': dtParseTimestamp(lr.get('pushedAt', EPOCH_STR)), # bogus date if last_project is n/a.
		'contribs':          contribs,
		'max_commits':       max_commits
	}

	# set last_project to false if more than 14 days ago, so not recent
	days_elapsed = (datetime.now()-retVal['last_project_date']).days
	if days_elapsed > 14:
		retVal['last_project'] = False

	# print values
	pprint(retVal)

	return retVal




# Main thread
# ==============================================================

# print jinja and python version
print('Script is running jinja v{} on Python v{}'.format(jinja2_version,python_version()))

# load config file
with open("config.json", "r", encoding='utf-8') as fp:
	config = json.load(fp)

# prep query data
GITHUB_API_KEY = config['apikey']
if len(sys.argv) > 1:
	# check if we provided one as a command parameter
	GITHUB_API_KEY = sys.argv[1]
query = file2str(config['queryfile']) \
	.replace('$USERNAME$', config['username']) \
	.replace('$TIMESTAMP_7DAYSAGO$', (datetime.now() - timedelta(7)).isoformat()) \
	.replace('$TIMESTAMP_YESTERDAY$', (datetime.now() - timedelta(1)).isoformat())

# get data
print('running GitHub GraphQL query ...\n')
result = run_query(query)

# process data
userdata = GitHubStats(result, config['ignore_repos'])
GH_Data = {
	'user': userdata,
	'days': 7,
	'support': True,
	'commit_sparkline': gen_SparklineSVG(userdata['contribs'])
}

# setup jinja2
print('\nrunning jinja2 ...')
G_j2_env = Environment( loader=FileSystemLoader('.') )
G_j2_env.globals['DATETIME_NOW'] = datetime.now()
G_j2_env.filters['shortnum'] = shortnum
G_j2_env.filters['smarttruncate'] = smarttruncate

# generate / render badge.html
renderSaveAs('badge.j2','badge.html',GH_Data)
