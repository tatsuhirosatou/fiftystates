import re

from fiftystates.scrape import NoDataForYear
from fiftystates.scrape.legislators import LegislatorScraper, Legislator
from fiftystates.scrape.tx.utils import clean_committee_name

import lxml.html


class TXLegislatorScraper(LegislatorScraper):
    state = 'tx'

    def scrape(self, chamber, year):
        if year != '2009':
            raise NoDataForYear(year)

        if chamber == 'upper':
            self.scrape_senators(year)
        else:
            self.scrape_reps(year)

    def scrape_senators(self, year):
        senator_url = 'http://www.senate.state.tx.us/75r/senate/senmem.htm'
        with self.urlopen(senator_url) as page:
            root = lxml.html.fromstring(page)
            root.make_links_absolute(senator_url)

            for el in root.xpath('//table[@summary="senator identification"]'):
                sen_link = el.xpath('tr/td[@headers="senator"]/a')[0]
                full_name = sen_link.text
                district = el.xpath('string(tr/td[@headers="district"])')
                party = el.xpath('string(tr/td[@headers="party"])')

                leg = Legislator('81', 'upper', district, full_name,
                                 party=party)
                leg.add_source(senator_url)

                details_url = sen_link.attrib['href']
                with self.urlopen(details_url) as details_page:
                    details = lxml.html.fromstring(details_page)
                    details.make_links_absolute(details_url)

                    try:
                        img = details.xpath(
                            "//img[contains(@name, 'District')]")[0]
                        leg['photo_url'] = img.attrib['src']
                    except IndexError:
                        # no photo
                        pass

                    try:
                        comms = details.xpath("//h2[contains(text(), "
                                              "'Committee Membership')]")[0]
                        comms = comms.getnext()
                        for comm in comms.xpath('li/a'):
                            comm_name = comm.text
                            if comm.tail:
                                comm_name += comm.tail

                            comm_name = clean_committee_name(comm_name)
                            leg.add_role('committee member', '81',
                                         committee=comm_name)
                    except IndexError:
                        # this legislator has no committee memberships yet
                        pass

                self.save_legislator(leg)

    def scrape_reps(self, year):
        rep_url = 'http://www.house.state.tx.us/members/welcome.php'
        with self.urlopen(rep_url) as page:
            root = lxml.html.fromstring(page)
            root.make_links_absolute(rep_url)

            for el in root.xpath('//form[@name="frmMembers"]/table/tr')[1:]:
                full_name = el.xpath('string(td/a/font/span)')
                district = el.xpath('string(td[2]/span)')
                county = el.xpath('string(td[3]/span)')

                if full_name.startswith('District'):
                    # Ignore empty seats
                    continue

                leg = Legislator('81', 'lower', district, full_name)
                leg.add_source(rep_url)

                # Is there anything out there that handles meta refresh?
                redirect_url = el.xpath('td/a')[0].attrib['href']
                details_url = redirect_url
                with self.urlopen(redirect_url) as redirect_page:
                    redirect = lxml.html.fromstring(redirect_page)

                    try:
                        filename = redirect.xpath(
                            "//meta[@http-equiv='refresh']")[0].attrib[
                            'content']

                        filename = filename.split('0;URL=')[1]

                        details_url = details_url.replace('welcome.htm',
                                                          filename)
                    except:
                        # The Speaker's member page does not redirect.
                        # The Speaker is not on any committees
                        # so we can just continue with the next member.
                        self.save_legislator(leg)
                        continue

                with self.urlopen(details_url) as details_page:
                    details = lxml.html.fromstring(details_page)
                    details.make_links_absolute(details_url)

                    comms = details.xpath(
                        "//b[contains(text(), 'Committee Assignments')]/"
                        "..//a")

                    for comm in comms:
                        comm_name = clean_committee_name(comm.text)

                        if re.match('Authored|Sponsored|Co-|other sessions',
                                    comm_name):
                            # A couple representative pages are broken and
                            # include links to authored/sponsored bills
                            # under committees
                            continue

                        leg.add_role('committee member', '81',
                                     committee=comm_name)

                self.save_legislator(leg)