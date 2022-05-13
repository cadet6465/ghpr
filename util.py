import os
import re
import json
import shutil
import requests
from pathlib import Path

base_url = 'https://api.github.com/'
pulls_url_template = base_url + 'repos/{owner}/{repo}/pulls?state=closed&sort=created&direction=asc&per_page={per_page}&page={page}'
pull_url_template = base_url + 'repos/{owner}/{repo}/pulls/{pull_number}'
issue_url_template = base_url + 'repos/{owner}/{repo}/issues/{issue_number}'
repo_path_template = os.path.join('{dst_dir}', '{owner}', '{repo}')
pulls_path_template = os.path.join('{dst_dir}', '{owner}', '{repo}', 'pulls-page-{page}.json')
pull_path_template = os.path.join('{dst_dir}', '{owner}', '{repo}', 'pull-{pull_number}.json')
issue_path_template = os.path.join('{dst_dir}', '{owner}', '{repo}', 'issue-{issue_number}.json')
ghpr_path_template = os.path.join('./result', '{owner}_{repo}_GHPR.txt')
owner_path_template = os.path.join('{src_dir}', '{owner}')
repo_path_template = os.path.join('{src_dir}', '{owner}', '{repo}')
devided_file_template = './result/{pro_name}_{type}.txt'

linked_keyword_pattern_template = r'\b(?:fix|fixes|fixed|resolve|resolves|resolved)\b'
modify_file_template = r'^diff\s*'
raw_file_url_template = 'https://github.com/{owner}/{repo}/raw/{sha}/{filename}'
get_function_name_template = r'^ func \s*'
get_changed_part_template = r'^@@\s*'



token = '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'

def has_keyword(s):
    re_tmp = re.compile(linked_keyword_pattern_template, flags=re.IGNORECASE)
    result = re_tmp.findall(s)
    if len(result) == 0 :
        return False
    return True


def extract_linked_issue_numbers(pull_body):
    if pull_body is None:
        return []
    return pull_body.split('/')[-1]

def save_json(obj, path):
    with open(path, 'w') as f:
        json.dump(obj, f, indent=2, sort_keys=True)

def ensure_dir_exists(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    Path(path).mkdir(parents=True, exist_ok=True)

class TooManyRequestFailures(Exception):
    pass

def is_related_with_defect(p):
    is_defect = False
    # merged and closed into master branch
    if p['merged_at'] and p['state'] == 'closed':
            #is commit labeled into bug fixing
        try :
            if (len(p.get('labels')) != 0 and p.get('labels')[0]['name'] == 'bug') or\
                    (p['body'] != None and has_keyword(p['body'])) or\
                    (p['title'] != None and has_keyword(p['title'])) :
                is_defect = True
        except Exception as e :
            print('check defect related error')
            print(e)
            is_defect = False
    return is_defect

def is_modify_go(diff_result):
    is_go_modi = False
    full_text = diff_result.text
    lines = full_text.split('\n')
    num_go = 0
    for line in lines:
        if modify_go_scan(line):
            is_go_modi = True
            num_go += 1
    return is_go_modi, num_go

def modify_go_scan(s):
    re_tmp = re.compile(modify_file_template)
    result = re_tmp.findall(s)
    is_modi_go = False
    if len(result) != 0 :
        try :
            filename = s.split()[2]
        except :
            print(s)
        filetype = (filename.split('/')[-1]).split('.')[-1]
        if filetype == 'go':
            is_modi_go = True
    return is_modi_go




def sorted_owner_repo_pairs(src_dir):
    pairs = [] # [(owner1,repo1), (owner2,repo2)]
    owners = os.listdir(src_dir)
    owners.sort()
    for owner in owners:
        repos = os.listdir(owner_path_template.format(src_dir=src_dir, owner=owner))
        repos.sort()
        for repo in repos:
            pairs.append((owner, repo))
    return pairs

def sorted_pull_numbers(src_dir, owner, repo):
    filenames = os.listdir(repo_path_template.format(src_dir=src_dir, owner=owner, repo=repo))
    pull_numbers = [int(f[5:-5]) for f in filenames if f.startswith('pull-')]
    pull_numbers.sort()
    return pull_numbers

def read_json(path):
    with open(path, 'r') as f:
        return json.load(f)





def _dataset_row(issue, pull):
    if issue.get('body') is None:
        issue_body_md = ''
        issue_body_plain = ''
    else:
        issue_body_md = issue['body']
        issue_body_plain = _md_to_text(issue_body_md)
    issue_label_ids = ','.join(str(l['id']) for l in issue['labels'])
    return [
        pull['base']['repo']['id'],
        issue['number'],
        issue['title'],
        issue_body_md,
        issue_body_plain,
        _iso_to_unix(issue['created_at']),
        issue['user']['id'],
        _author_association_value[issue['author_association']],
        issue_label_ids,
        pull['number'],
        _iso_to_unix(pull['created_at']),
        _iso_to_unix(pull['merged_at']),
        pull['comments'],
        pull['review_comments'],
        pull['commits'],
        pull['additions'],
        pull['deletions'],
        pull['changed_files'],
    ]
