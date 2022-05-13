import pandas as pd
import requests
import re
from tqdm import tqdm
import time
import util
import signal
import sys
import json
import logging



class Writer(object):

    def __init__(self,
                 token = util.token,
                 dst_dir='repos',
                 max_request_tries=5000,
                 request_retry_wait_secs=10):
        self.dst_dir = dst_dir
        self.max_request_tries = max_request_tries
        self.request_retry_wait_secs = request_retry_wait_secs
        self._headers = {
            'Accept': 'application/vnd.github.v3+json',
        }


        if token is not None:
            self._headers['Authorization'] = 'token ' + token
        self._interrupted = False

        def sigint_handler(signal, frame):
            if self._interrupted:
                print('\nForced exit')
                sys.exit(2)
            self._interrupted = True
            print('\nInterrupted, finishing current page\nPress interrupt key again to force exit')

        signal.signal(signal.SIGINT, sigint_handler)


    def _get(self, url):
        tries = 0
        while True:
            r = self._load_from_url(url)
            if r is not None:
                full_text = r.text
                lines = full_text.split('\n')
                return lines
            tries += 1
            if tries >= self.max_request_tries:
                print('Request failed {} times, aborting'.format(tries))
                raise util.TooManyRequestFailures('{} request failures for {}'.format(tries, url))
            print('Request failed {} times, retrying in {} seconds'.format(tries, self.request_retry_wait_secs))
            time.sleep(self.request_retry_wait_secs)

    def _load_from_url(self, url):
        try :
            get_result = requests.get(url, headers=self._headers)
            if not get_result.ok:
                # print('Get: not ok: {} {} {} {}'.format(url, get_result.status_code, get_result.headers, get_result.text))
                if 'X-Ratelimit-Remaining' in get_result.headers and int(get_result.headers['X-Ratelimit-Remaining']) < 1 and 'X-Ratelimit-Reset' in get_result.headers:
                    ratelimit_wait_secs = int(get_result.headers['X-Ratelimit-Reset']) - int(time.time()) + 1
                    print('Rate limit reached, waiting {} secs for reset'.format(ratelimit_wait_secs))
                    time.sleep(ratelimit_wait_secs)
                    return self._load_from_url(url)
            return get_result
        except Exception as e:
            print(e)
            return None



    def _find_function_name(self, diff_url):
        #is it modifying go file??

        def _modify_go_scan(s):
            re_tmp = re.compile(util.modify_file_template)
            result = re_tmp.findall(s)
            return_filename = None
            if len(result) != 0:
                filename = s.split()[2][2:]
                filetype = (filename.split('/')[-1]).split('.')[-1]
                if filetype == 'go':
                    return_filename = filename
            return return_filename

        #is it modifying function??
        def _get_function_name(s):
            re_tmp = re.compile(util.get_changed_part_template)
            re_tmp2 = re.compile(util.get_function_name_template)
            result = re_tmp.findall(s)
            modi_function_name = None
            if len(result) != 0:
                change_part_name = s.split('@@')[-1]
                re_temp = re_tmp2.findall(change_part_name)
                if len(re_temp) != 0:
                    modi_function_name= change_part_name[1:]
            return modi_function_name

        lines = self._get(diff_url)
        result_list = []
        temp_file_name = None
        #diff line by line
        for line in lines:
            modify_file_nm = _modify_go_scan(line)
            modify_function_nm = _get_function_name(line)
            #check modifying .go
            if modify_file_nm !=None:
                temp_file_name = [modify_file_nm,False]
            try:
                # Remove filenmae doubling
                if temp_file_name != None  and modify_function_nm !=None:
                    if temp_file_name[-1] == False:
                        result_list.append(temp_file_name[0])
                        temp_file_name[-1] = True
                    if result_list[-1].strip() != modify_function_nm.strip():
                        result_list.append(modify_function_nm)

            except Exception as e :
                print(modify_file_nm)
                print(temp_file_name)
                print(result_list)
                print("Make result list error")
                print(e)
                print(diff_url)
                print(line)
                continue
        # result_list = [filename, function name1, 2,  filename ]
        return result_list

    def _write_dataset(self, result_list,owner,repo,defective_code_sha,clean_code_sha,file,title):

        def _getfunction_name(full_function_name):
            sliced_name = full_function_name.split()
            if sliced_name[1][0] != '(':
                return sliced_name[1].split('(')[0]
            else:
                return sliced_name[3].split('(')[0]
        def _find_modi_func_source(lines,function_name):
            line_index = 0
            start_index = 0
            start_function_at_index=-1
            end_index = 0

            for line in lines:
                funcname_start_index = line.find(function_name+"(")
                func_start_index = line.find('func')

                if func_start_index != -1 and funcname_start_index != -1 and func_start_index<funcname_start_index:
                    start_index = line_index
                    start_function_at_index=func_start_index
                if start_function_at_index != -1 and start_function_at_index == line.find('}'):
                    end_index = line_index
                    break
                line_index += 1
            return start_index, end_index

        num_go_file = 0
        num_fun = 0

        for result in result_list:
            if result.split('.')[-1] == 'go':
                filename = result.replace('/', '%2F')
                defective_code_url = util.raw_file_url_template.format(owner=owner, repo=repo, sha=defective_code_sha,
                                                                   filename=filename)
                clean_code_url = util.raw_file_url_template.format(owner=owner, repo=repo, sha=clean_code_sha,
                                                               filename=filename)
                defective_code_lines = self._get(defective_code_url)
                clean_code_lines = self._get(clean_code_url)
                num_go_file += 1
            else :
                try :
                    function_name = _getfunction_name(result)
                except Exception as e :
                    print(e)
                    print(result)
                    function_name = "Error_func_name"
                def_start,def_end = _find_modi_func_source(defective_code_lines,function_name)
                cln_start,cln_end = _find_modi_func_source(clean_code_lines,function_name)
                if def_start>def_end or cln_start>cln_end:
                    print("Search start and end point error")
                    print(defective_code_url)
                    print(function_name)
                    print(def_start,def_end)
                    print(clean_code_url)
                    print(function_name)
                    print(cln_start,cln_end)
                    continue
                dective_code = ''.join(
                    "" if i.find('//') != -1 else i for i in defective_code_lines[def_start:def_end + 1])
                cln_code = ''.join(
                    "" if i.find('//') !=-1 else i for i in clean_code_lines[cln_start:cln_end + 1])


                if dective_code != cln_code:
                    def_string ="1" + '<CODESPLIT>'+ defective_code_url +'<CODESPLIT>' + str(function_name) + '<CODESPLIT>' + title + '<CODESPLIT>'+dective_code
                    cln_string ="0" + '<CODESPLIT>'+ clean_code_url +'<CODESPLIT>' + str(function_name) + '<CODESPLIT>' + title + '<CODESPLIT>'+cln_code
                    try:
                        file.write(def_string)
                        file.write('\n')
                        file.write(cln_string)
                        file.write('\n')
                        num_fun += 1
                    except Exception as e:
                        print("write error")
                        print(e)
                        print(def_string)
                        print(cln_string)
                else :
                    continue
        return num_go_file,num_fun

    def writer(self,src_dir):
        repo_full_names = []
        repo_num_rows = []
        owner_repo_pairs = util.sorted_owner_repo_pairs(src_dir)
        num_repos = len(owner_repo_pairs)
        for i, (owner, repo) in enumerate(owner_repo_pairs):
            repo_full_name = '{}/{}'.format(owner, repo)
            repo_full_names.append(repo_full_name)
            repo_num_rows.append(0)
            util.ensure_dir_exists('./result')
            dataset_path = util.ghpr_path_template.format(owner= owner, repo= repo)
            dataset_file =open(dataset_path,'w',newline='',encoding='UTF-8')

            print('{} ({:,}/{:,})'.format(repo_full_name, i + 1, num_repos))
            for pull_number in tqdm(util.sorted_pull_numbers(src_dir, owner, repo)):
                pull = util.read_json(util.pull_path_template.format(dst_dir=self.dst_dir, owner=owner, repo=repo,
                                                                     pull_number=pull_number))
                diff_url = pull['diff_url']
                clean_code_sha = pull['head']['sha']
                defective_code_sha = pull['base']['sha']
                pull_title = pull['title']
                modi_file_function_list = self._find_function_name(diff_url)
                num_go_file,num_fun = self._write_dataset(modi_file_function_list,owner,repo,defective_code_sha,clean_code_sha,dataset_file,pull_title)
        return num_go_file,num_fun


def main():
    writer = Writer()
    a,b=writer.writer(src_dir='./repos')
    print(a,b)





if __name__ == '__main__':
    main()