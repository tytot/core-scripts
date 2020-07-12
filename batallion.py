#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import datetime
import optparse
import csv

from core import pycore
from core.misc import ipaddr
from core.constants import *
from core.api import coreapi
from array import *
import time
import threading

COMPANIES_IN_BATALLION = 1
PLATOONS_IN_COMPANY = 1
HOSTS_IN_PLATOON = 3


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


class MovementConfig:
    def __init__(self, node, start_pos, end_pos, start_time, end_time):
        self.node = node
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.start_time = start_time
        self.end_time = end_time


def movement_thread(batallion, session, refresh_ms):
    def move_nodes(configs):
        elapsed = 0
        while configs:
            for config in configs:
                current = config[0]
                if elapsed >= current.start_time:
                    lerp_amount = (elapsed - current.start_time) / \
                        (current.end_time - current.start_time)
                    delta = (current.end_pos[0] - current.start_pos[0],
                             current.end_pos[1] - current.start_pos[1], 0)
                    new_pos = (current.start_pos[0] + lerp_amount * delta[0],
                               current.start_pos[1] + lerp_amount * delta[1], 0)
                    current.node.setposition(new_pos[0], new_pos[1], 0)
                    msg = current.node.tonodemsg(flags=0)
                    session.broadcastraw(None, msg)
                    session.sdt.updatenode(
                        current.node.objid, flags=0, x=new_pos[0], y=new_pos[1], z=new_pos[2])
                    if elapsed + 0.001 * refresh_ms >= current.end_time:
                        del config[0]
                        if not config:
                            configs.remove(config)
            elapsed += 0.001 * refresh_ms
            time.sleep(0.001 * refresh_ms)

    # node1 = batallion.companies[1].platoons[1].hosts[1]
    # node2 = batallion.companies[1].platoons[1].hosts[2]
    # node3 = batallion.companies[1].platoons[1].hosts[3]
    # configs = [
    #     [
    #         MovementConfig(node1, node1.position.get(), (700, 700, 0), 0, 20), 
    #         MovementConfig(node1, (700, 700, 0), (100, 100, 0), 20, 40)
    #     ], 
    #     [
    #         MovementConfig(node2, node2.position.get(), (700, 100, 0), 0, 20),
    #         MovementConfig(node2, (700, 100, 0), (11, 100, 0), 20, 50)
    #     ], 
    #     [
    #         MovementConfig(node3, node3.position.get(), (300, 700, 0), 0, 20)
    #     ]
    # ]
    # move_nodes(configs)

    def pos_to_tuple(pos):
        coords = pos.split()
        return (coords[0], coords[1], 0)

    with open('batallion_movement.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        configs = [[] for i in xrange(len(csv_reader))]
        times = csv_reader[0]
        line = 0
        for row in csv_reader:
            if line > 0:
                octets = row[0].split('.')
                node = batallion.companies[octets[0]].platoons[octets[1]].hosts[octets[2]]
                last_waypoint_index = None
                for i in xrange(1, len(row)):
                    if row[i]:
                        if (last_waypoint_index is None):
                            if (i != 1):
                                configs[line - 1].append(MovementConfig(node, node.position.get(), pos_to_tuple(row[i]), 0, times[i]))
                        else:
                            configs[line - 1].append(MovementConfig(node, pos_to_tuple(row[last_waypoint_index]), pos_to_tuple(row[i]), times[last_waypoint_index], times[i]))
                        last_waypoint_index = i
                line += 1
        move_nodes(configs)


def main():

    start = datetime.datetime.now()

    session = pycore.Session(persistent=True)
    if 'server' in globals():
        server.addsession(session)
    batallion = Batallion(session, 1)

    num_nodes = COMPANIES_IN_BATALLION * \
        ((PLATOONS_IN_COMPANY * (HOSTS_IN_PLATOON + 3)) + 2) + 1
    session.node_count = num_nodes
    print('Finished creating %d nodes.' % num_nodes)

    thread = threading.Thread(target=movement_thread,
                              args=(batallion, session, 125,))
    thread.start()
    thread.join()

    print("elapsed time: %s" % (datetime.datetime.now() - start))


if __name__ == '__main__' or __name__ == '__builtin__':
    main()
