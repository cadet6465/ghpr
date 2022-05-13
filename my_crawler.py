import inspect
import logging
import traceback
import requests
import signal
import sys
import time
import util


class Crawler(object):

    def __init__(self,
                 token= util.token,
                 dst_dir='repos',
                 per_page=100,
                 save_pull_pages=True,
                 max_request_tries=5000,
                 request_retry_wait_secs=10):

        self.dst_dir = dst_dir
        self.per_page = per_page
        self.save_pull_pages = save_pull_pages
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

    def _try_to_get(self, url):
        try:
            r = requests.get(url, headers=self._headers)
            if not r.ok:
                logging.error('Get: not ok: {} {} {} {}'.format(url, r.status_code, r.headers, r.text))
                print(r.text)
                if 'X-Ratelimit-Remaining' in r.headers and int(
                        r.headers['X-Ratelimit-Remaining']) < 1 and 'X-Ratelimit-Reset' in r.headers:
                    ratelimit_wait_secs = int(r.headers['X-Ratelimit-Reset']) - int(time.time()) + 1
                    logging.info('Get: waiting {} secs for rate limit reset'.format(ratelimit_wait_secs))
                    print('Rate limit reached, waiting {} secs for reset'.format(ratelimit_wait_secs))
                    time.sleep(ratelimit_wait_secs)
                    return self._try_to_get(url)
                return None
            rj = r.json()
        except Exception as e:
            logging.error('Get: exception: {} {}'.format(url, e))
            return None
        if isinstance(rj, dict) and 'message' in rj:
            logging.error('Get: error: {} {}'.format(url, rj))
            return None
        return rj

    def _get(self, url):
        tries = 0
        while True:
            r = self._try_to_get(url)
            if r is not None:
                return r
            tries += 1
            if tries >= self.max_request_tries:
                print('Request failed {} times, aborting'.format(tries))
                raise util.TooManyRequestFailures('{} request failures for {}'.format(tries, url))
            print('Request failed {} times, retrying in {} seconds'.format(tries, self.request_retry_wait_secs))
            time.sleep(self.request_retry_wait_secs)


    def crawl(self, owner, repo, start_page=1):

        logging.info('Crawl: starting {} {}/{}'.format(start_page, owner, repo))
        print('Starting from page {} ({}/{})'.format(start_page, owner, repo))
        util.ensure_dir_exists(util.repo_path_template.format(dst_dir=self.dst_dir, owner=owner, repo=repo))
        # linked_issues_regex = util.make_linked_issues_regex(owner, repo)

        page = start_page

        num_issues = 0
        num_pulls = 0
        num_defect_relate_pulls = 0
        num_modi_go_pulls = 0
        total_modi_go_file = 0

        self._interrupted = False
        while not self._interrupted:
            pulls = self._get(util.pulls_url_template.format(per_page=self.per_page, owner=owner, repo=repo, page=page))

            #save all pull into json
            if self.save_pull_pages:
                util.save_json(pulls, util.pulls_path_template.format(dst_dir=self.dst_dir, owner=owner, repo=repo, page=page))

            for p in pulls:
                num_pulls += 1
                if util.is_related_with_defect(p):
                    num_defect_relate_pulls += 1

                    diff_result = requests.get(p['diff_url'], headers=self._headers)
                    is_modi_go, num_modi_go = util.is_modify_go(diff_result)
                    total_modi_go_file += total_modi_go_file
                    if is_modi_go:
                        num_modi_go_pulls += 1
                        p['num_modi_go'] = num_modi_go
                        linked_issue_numbers = util.extract_linked_issue_numbers(p.get('issue_url'))
                        print(p.get('issue_url'))
                        print(linked_issue_numbers)
                        if linked_issue_numbers:
                            pull_number = p['number']
                            p['linked_issue_numbers'] = linked_issue_numbers
                            util.save_json(p, util.pull_path_template.format(dst_dir=self.dst_dir, owner=owner, repo=repo, pull_number=pull_number))
                            num_pulls += 1
                            # for issue_number in linked_issue_numbers:
                            issue = self._get(p.get('issue_url'))
                            # print('issue label :', '' if len(issue.get('labels')) == 0 else issue.get('labels')[0]['name'])
                            util.save_json(issue, util.issue_path_template.format(dst_dir=self.dst_dir, owner=owner, repo=repo, issue_number=linked_issue_numbers))
                            num_issues += 1
            logging.info('Crawl: finished {} {}/{}'.format(page, owner, repo))
            print('Page {} finished ({}/{})'.format(page, owner, repo))
            if len(pulls) < self.per_page:
                logging.info('Crawl: finished all, {} issues {} pulls {}/{}'.format(num_issues, num_pulls, owner, repo))
                print('All pages finished, saved {} issues and {} pull requests ({}/{})'.format(num_issues, num_pulls, owner, repo))
                print('Total_PR : {} , Defect_PR : {}, Modi_go_PR : {} , Total_modi_go_file : {}'.format(num_pulls,num_defect_relate_pulls,num_modi_go_pulls,total_modi_go_file))
                return
            page += 1


def main():
    repos = ['yomorun/yomo']
    start_page = 1
    crawler = Crawler()

    for r in repos:
        n = r.find('/')
        owner = r[:n]
        repo = r[n+1:]

        try:
            crawler.crawl(owner, repo, start_page=start_page)

        except Exception as e:
            logging.error('Main: exception: {}/{} {}'.format(owner, repo, e))
            print('Terminated with error: {} ({}/{})'.format(e, owner, repo))
            logging.error(traceback.format_exc())


if __name__ == '__main__':
    main()
