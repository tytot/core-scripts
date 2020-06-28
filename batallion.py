#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import datetime
import optparse

from core import pycore
from core.misc import ipaddr
from core.constants import *
from array import *
import time

batallion = None
COMPANIES_IN_BATALLION = 6
PLATOONS_IN_COMPANY = 5
HOSTS_IN_PLATOON = 16


class Platoon:
    def __init__(self, session, batallion_index, company_index, platoon_index):
        self.hosts = [None]
        self.batallion_index = batallion_index
        self.company_index = company_index
        self.platoon_index = platoon_index
        index = (company_index - 1) * PLATOONS_IN_COMPANY + platoon_index
        x = 150 * (company_index - 1)
        y = 100 * (platoon_index - 1)
        LOCATIONS = [
            [x + 10, y],
            [x + 20, y],
            [x + 30, y],
            [x + 40, y],
            [x + 50, y + 10],
            [x + 50, y + 20],
            [x + 50, y + 30],
            [x + 50, y + 40],
            [x + 40, y + 50],
            [x + 30, y + 50],
            [x + 20, y + 50],
            [x + 10, y + 50],
            [x, y + 40],
            [x, y + 30],
            [x, y + 20],
            [x, y + 10],
        ]

        local_wlan = session.addobj(cls=pycore.nodes.WlanNode,
                                    name='wlan%d' % index)
        local_wlan.setposition(x=x + 25, y=y + 25)
        self.wlan = local_wlan
        r = session.addobj(cls=pycore.nodes.CoreNode,
                           name='r%d' % index)
        r.setposition(x=x + 75, y=y + 25)
        last_octet = HOSTS_IN_PLATOON + 1
        r.newnetif(local_wlan, [
                   '%d.%d.%d.%d/24' % (batallion_index, company_index, platoon_index, last_octet)])
        session.services.addservicestonode(r, 'router', None, False)
        self.router = r

        for i in xrange(1, HOSTS_IN_PLATOON + 1):
            self.connect_host(session, LOCATIONS[i - 1])

    def connect_host(self, session, pos):
        host_index = len(self.hosts)
        index = (self.company_index - 1) * (HOSTS_IN_PLATOON * PLATOONS_IN_COMPANY) + \
            (self.platoon_index - 1) * HOSTS_IN_PLATOON + host_index
        host = session.addobj(cls=pycore.nodes.CoreNode,
                              name='h%d' % index)
        host.setposition(x=pos[0], y=pos[1])
        host.newnetif(self.wlan, [
                      '%d.%d.%d.%d/24' % (self.batallion_index, self.company_index, self.platoon_index, len(self.hosts))])
        session.services.addservicestonode(host, 'host',
                                           'DefaultRoute|SSH', False)
        self.hosts.append(host)


class Company:
    def __init__(self, session, batallion_index, company_index):
        self.platoons = [None]
        self.batallion_index = batallion_index
        self.company_index = company_index
        router_index = COMPANIES_IN_BATALLION * PLATOONS_IN_COMPANY + company_index
        r = session.addobj(cls=pycore.nodes.CoreNode,
                           name='r%d' % router_index)
        r_x = 150 * (company_index - 1) + 100
        r_y = 50 * PLATOONS_IN_COMPANY
        r.setposition(x=r_x, y=r_y)
        session.services.addservicestonode(r, 'router', None, False)
        self.router = r

        for i in xrange(1, PLATOONS_IN_COMPANY + 1):
            self.connect_platoon(session)

    def connect_platoon(self, session):
        platoon_index = len(self.platoons)
        platoon = Platoon(session, self.batallion_index, self.company_index,
                          platoon_index)
        index = (self.company_index - 1) * PLATOONS_IN_COMPANY + platoon_index
        wlan = session.addobj(cls=pycore.nodes.WlanNode,
                              name='t1wlan%d' % index)
        pr_pos = platoon.router.position.get()
        sr_pos = self.router.position.get()
        wlan_x = (pr_pos[0] + sr_pos[0]) / 2
        wlan_y = (pr_pos[1] + sr_pos[1]) / 2
        wlan.setposition(x=wlan_x, y=wlan_y)
        platoon.router.newnetif(
            wlan, ['%d.%d.%d.1/24' % (self.batallion_index, self.company_index, 4 + platoon_index)])
        self.router.newnetif(
            wlan, ['%d.%d.%d.2/24' % (self.batallion_index, self.company_index, 4 + platoon_index)])
        self.platoons.append(platoon)


class Batallion:
    def __init__(self, session, batallion_index):
        self.companies = [None]
        self.batallion_index = batallion_index
        router_index = COMPANIES_IN_BATALLION * \
            PLATOONS_IN_COMPANY + COMPANIES_IN_BATALLION + 1
        r = session.addobj(cls=pycore.nodes.CoreNode,
                           name='r%d' % router_index)
        r_x = 75 * COMPANIES_IN_BATALLION
        r_y = 100 * PLATOONS_IN_COMPANY + 50
        r.setposition(x=r_x, y=r_y)
        session.services.addservicestonode(r, 'router', None, False)
        self.router = r

        for i in xrange(1, COMPANIES_IN_BATALLION + 1):
            self.connect_company(session)

    def connect_company(self, session):
        company_index = len(self.companies)
        company = Company(session, self.batallion_index,
                          company_index)
        wlan = session.addobj(cls=pycore.nodes.WlanNode,
                              name='t2wlan%d' % company_index)
        cr_pos = company.router.position.get()
        sr_pos = self.router.position.get()
        wlan_x = (cr_pos[0] + sr_pos[0]) / 2
        wlan_y = (cr_pos[1] + sr_pos[1]) / 2
        wlan.setposition(x=wlan_x, y=wlan_y)
        company.router.newnetif(
            wlan, ['%d.%d.9.1/24' % (self.batallion_index, company_index)])
        self.router.newnetif(
            wlan, ['%d.%d.9.2/24' % (self.batallion_index, company_index)])
        self.companies.append(company)


def main():

    # usagestr = "usage: %prog [-h] [options] [args]"
    # parser = optparse.OptionParser(usage = usagestr)
    # parser.set_defaults(numnodes = 5)

    # parser.add_option("-n", "--numnodes", dest = "numnodes", type = int,
    #                   help = "number of nodes")

    # def usage(msg = None, err = 0):
    #     sys.stdout.write("\n")
    #     if msg:
    #         sys.stdout.write(msg + "\n\n")
    #     parser.print_help()
    #     sys.exit(err)

    # # parse command line options
    # (options, args) = parser.parse_args()

    # if options.numnodes < 1:
    #     usage("invalid number of nodes: %s" % options.numnodes)

    # for a in args:
    #     sys.stderr.write("ignoring command line argument: '%s'\n" % a)

    start = datetime.datetime.now()

    session = pycore.Session(persistent=True)
    if 'server' in globals():
        server.addsession(session)
    batallion = Batallion(session, 1)

    num_nodes = COMPANIES_IN_BATALLION * \
        ((PLATOONS_IN_COMPANY * (HOSTS_IN_PLATOON + 3)) + 2) + 1
    session.node_count = num_nodes
    print('Finished creating %d nodes.' % num_nodes)
    session.instantiate()

    print "elapsed time: %s" % (datetime.datetime.now() - start)

    # tests

    # nodes[1].setposition(x=500.0,y=300.0)


if __name__ == '__main__' or __name__ == '__builtin__':
    main()
