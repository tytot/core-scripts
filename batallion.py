#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import datetime
import optparse
import csv
import math
from random import seed
from random import randint

from core import pycore
from core.misc import ipaddr
from core.constants import *
from core.api import coreapi
from array import *
import time
import threading

COMPANIES_IN_BATALLION = 1
PLATOONS_IN_COMPANY = 5
HOSTS_IN_PLATOON = 4
MOVEMENT = True


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
            [x, y],
            [x + 50, y],
            [x + 50, y + 50],
            [x, y + 50]
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
        self.wlans = [None]

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
        self.wlans.append(wlan)
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
        self.wlans = [None]

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
        self.wlans.append(wlan)
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

    def __repr__(self):
        return '{}({!r}, {!r}, {!r}, {!r}, {!r})'.format(
            self.__class__.__name__,
            self.node.objid, self.start_pos, self.end_pos, self.start_time, self.end_time)


def movement_thread(configs, session, refresh_ms):
    elapsed = 0
    while configs:
        configs = [config for config in configs if config != []]
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
                if elapsed + 0.001 * refresh_ms > current.end_time:
                    del config[0]
        elapsed += 0.001 * refresh_ms
        time.sleep(0.001 * refresh_ms)


def ngon_verts(N, R):
    verts = [None]
    for i in xrange(0, N):
        verts.append([R * math.cos(2 * math.pi * i / N),
                      R * math.sin(2 * math.pi * i / N)])
    return verts


def generate_configs(batallion):
    def pos_to_tuple(pos):
        coords = pos.split()
        return (int(coords[0]), int(coords[1]), 0)

    configs = []

    with open('/home/linth1/core-scripts/batallion_movement.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        line = 0
        for row in csv_reader:
            if line == 0:
                times = row
                line += 1
            else:
                configs.append([])
                octets = row[0].split('.')
                node = batallion.companies[int(octets[1])
                                           ].platoons[int(octets[2])].hosts[int(octets[3])]
                last_waypoint_index = None
                for i in xrange(1, len(row)):
                    if row[i]:
                        if (last_waypoint_index is None):
                            if (i != 1):
                                configs[line - 1].append(MovementConfig(
                                    node, node.position.get(), pos_to_tuple(row[i]), 0, int(times[i])))
                        else:
                            configs[line - 1].append(MovementConfig(node, pos_to_tuple(
                                row[last_waypoint_index]), pos_to_tuple(row[i]), int(times[last_waypoint_index]), int(times[i])))
                        last_waypoint_index = i
                line += 1

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

    # print configs
    return configs


def generate_random_configs(batallion):
    WIDTH = 3840
    HEIGHT = 2160
    X_MI = 50
    Y_MI = (HEIGHT / WIDTH) * X_MI
    TIME = 60
    MAX_TIME_BT_WP = 20
    MAX_OFFSET = 200
    DISPL = 50

    configs = []
    global index
    index = 0

    def add_config(config):
        global index
        if (index >= len(configs)):
            configs.append([])
        configs[index].append(config)
        index += 1

    company = batallion.companies[1]
    c_start_pos = (MAX_OFFSET + DISPL, MAX_OFFSET + DISPL, 0)
    c_end_pos = (WIDTH - MAX_OFFSET - DISPL,
                 HEIGHT - MAX_OFFSET - DISPL, 0)
    c_delta = (c_end_pos[0] - c_start_pos[0], c_end_pos[1] - c_start_pos[1], 0)

    HOST_LOCS = ngon_verts(HOSTS_IN_PLATOON, DISPL)
    C_WLAN_LOCS = ngon_verts(PLATOONS_IN_COMPANY, DISPL)
    B_WLAN_LOCS = ngon_verts(COMPANIES_IN_BATALLION, DISPL)

    for platoon in company.platoons:
        if platoon is not None:
            p_start_time = 0
            p_offset = [randint(-MAX_OFFSET, MAX_OFFSET),
                        randint(-MAX_OFFSET, MAX_OFFSET)]
            p_start_pos = (
                c_start_pos[0] + p_offset[0], c_start_pos[1] + p_offset[1], 0)
            START_INDEX = index
            while p_start_time < TIME:
                index = START_INDEX
                p_end_time = min(
                    randint(p_start_time + 1, p_start_time + MAX_TIME_BT_WP), TIME)
                percentage = float(p_end_time) / TIME
                p_offset = [randint(-MAX_OFFSET, MAX_OFFSET),
                            randint(-MAX_OFFSET, MAX_OFFSET)]

                p_end_pos = (c_start_pos[0] + (percentage * c_delta[0]) + p_offset[0],
                             c_start_pos[1] + (percentage * c_delta[1]) + p_offset[1], 0)
                for i in xrange(1, HOSTS_IN_PLATOON + 1):
                    host = platoon.hosts[i]
                    add_config(MovementConfig(host, (p_start_pos[0] + HOST_LOCS[i][0], p_start_pos[1] + HOST_LOCS[i][1], 0), (
                        p_end_pos[0] + HOST_LOCS[i][0], p_end_pos[1] + HOST_LOCS[i][1], 0), p_start_time, p_end_time))

                add_config(MovementConfig(platoon.wlan, p_start_pos,
                           p_end_pos, p_start_time, p_end_time))
                add_config(MovementConfig(platoon.router, (p_start_pos[0], p_start_pos[1] + (2 * DISPL), 0), (
                    p_end_pos[0], p_end_pos[1] + (2 * DISPL), 0), p_start_time, p_end_time))

                p_start_time=p_end_time
                p_start_pos=p_end_pos
    add_config(MovementConfig(company.router, c_start_pos, c_end_pos, 0, TIME))
    for i in xrange(1, PLATOONS_IN_COMPANY + 1):
        c_wlan=company.wlans[i]
        add_config(MovementConfig(c_wlan, (c_start_pos[0] + C_WLAN_LOCS[i][0], c_start_pos[1] + C_WLAN_LOCS[i][1], 0), (
            c_end_pos[0] + C_WLAN_LOCS[i][0], c_end_pos[1] + C_WLAN_LOCS[i][1], 0), 0, TIME))

    add_config(MovementConfig(batallion.router, c_start_pos, c_end_pos, 0, TIME))
    for i in xrange(1, COMPANIES_IN_BATALLION + 1):
        b_wlan=batallion.wlans[i]
        add_config(MovementConfig(b_wlan, (c_start_pos[0] + B_WLAN_LOCS[i][0], c_start_pos[1] + B_WLAN_LOCS[i][1], 0), (
            c_end_pos[0] + B_WLAN_LOCS[i][0], c_end_pos[1] + B_WLAN_LOCS[i][1], 0), 0, TIME))

    return configs


def main():

    start=datetime.datetime.now()

    session=pycore.Session(persistent = True)
    if 'server' in globals():
        server.addsession(session)
    batallion=Batallion(session, 1)

    num_nodes=COMPANIES_IN_BATALLION * \
        ((PLATOONS_IN_COMPANY * (HOSTS_IN_PLATOON + 3)) + 2) + 1
    session.node_count=num_nodes
    print 'Finished creating %d nodes.' % num_nodes
    session.instantiate()

    if MOVEMENT:
        thread=threading.Thread(target = movement_thread,
                                  args = (generate_random_configs(batallion), session, 125,))
        thread.start()
        thread.join()

    print "elapsed time: %s" % (datetime.datetime.now() - start)


if __name__ == '__main__' or __name__ == '__builtin__':
    main()
