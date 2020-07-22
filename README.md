# github-badge-2
 
Simpler implementation, utilizing GitHub's GraphQL API, and fork of:
https://github.com/berkerpeksag/github-badge

## Usage
Simply update `config.json` with your username and github api_key that has user repo read access and user activity. Run the `generate_badge.py` script with python v3.7+, with `jinja2` and `requests` installed.

Then, set up a cron job or whatever you can use for a recurring / scheduled tasks to run the script periodically (something like every 24hrs) to update the generated `badge.html`.

## Preview
![example](preview.png)