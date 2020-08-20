#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
import datetime
import csv
import math
import time
import threading
from random import seed
from random import randint
from itertools import combinations
from array import *

from core import pycore
from core import location
from core.misc import ipaddr
from core.constants import *
from core.api import coreapi
from core.mobility import BasicRangeModel

# START SETTINGS
COMPANIES_IN_BATALLION = 4
PLATOONS_IN_COMPANY = 2
HOSTS_IN_PLATOON = 2
MOVEMENT = True
REFRESH_MS = 500

WIDTH = 3840
HEIGHT = 2160
X_MI = 50

TIME = 60
C_MAX_TIME_BT_WP = 40
P_MAX_TIME_BT_WP = 20
MAX_C_DISPL = 2000
MAX_P_DISPL = 2000
WLAN_RANGE = 20000
# END SETTINGS

SCALE = X_MI * 1609 / WIDTH
MAX_C_DISPL = MAX_C_DISPL / SCALE
MAX_P_DISPL = MAX_P_DISPL / SCALE
WLAN_RANGE = WLAN_RANGE / SCALE


def ngon_verts(N, R):
    verts = []
    for i in xrange(0, N):
        verts.append([R * math.cos(2 * math.pi * i / N),
                      R * math.sin(2 * math.pi * i / N)])
    return verts


class Platoon:
    def __init__(self, session, pos, wlan, batallion_index, company_index, platoon_index):
        self.hosts = [None]
        self.batallion_index = batallion_index
        self.company_index = company_index
        self.platoon_index = platoon_index

        verts = ngon_verts(HOSTS_IN_PLATOON, MAX_P_DISPL / 10)
        LOCATIONS = [(pos[0] + verts[i][0], pos[1] + verts[i][1], 0)
                     for i in xrange(HOSTS_IN_PLATOON)]

        for i in xrange(HOSTS_IN_PLATOON):
            self.connect_host(session, LOCATIONS[i], wlan)

    def connect_host(self, session, host_pos, wlan):
        host_index = len(self.hosts)
        index = (self.company_index - 1) * (HOSTS_IN_PLATOON * PLATOONS_IN_COMPANY) \
            + (self.platoon_index - 1) * HOSTS_IN_PLATOON + host_index
        host = session.addobj(cls=pycore.nodes.CoreNode,
                              name='h%d' % index)
        host.setposition(x=host_pos[0], y=host_pos[1])
        host.newnetif(wlan, [
            '%d.%d.1.%d/24' % (self.batallion_index, self.company_index, index)])
        self.hosts.append(host)


class Company:
    def __init__(self, session, pos, batallion_index, company_index):
        self.platoons = [None]
        self.hosts = [None]
        self.batallion_index = batallion_index
        self.company_index = company_index
        self.twlans = []

        p_verts = ngon_verts(PLATOONS_IN_COMPANY, MAX_P_DISPL / 2)
        P_LOCATIONS = [(pos[0] + p_verts[i][0], pos[1] + p_verts[i][1], 0)
                       for i in xrange(PLATOONS_IN_COMPANY)]

        r_verts = ngon_verts(COMPANIES_IN_BATALLION * 2, MAX_P_DISPL / 10)

        self.wlan = session.addobj(cls=pycore.nodes.WlanNode,
                                   name='uwlan%d' % company_index)
        self.wlan.setposition(x=pos[0], y=pos[1])
        values = list(BasicRangeModel.getdefaultvalues())
        values[0] = str(WLAN_RANGE)
        self.wlan.setmodel(BasicRangeModel, values)

        self.routers = [None]
        for i in xrange(COMPANIES_IN_BATALLION * 2):
            r_index = (self.company_index - 1) * \
                (COMPANIES_IN_BATALLION * 2) + 1 + i
            router = session.addobj(cls=pycore.nodes.CoreNode,
                                    name='r%d' % r_index)
            router.setposition(x=pos[0] + r_verts[i][0],
                               y=pos[1] + r_verts[i][1])
            session.services.addservicestonode(router, 'router', None, False)
            index = HOSTS_IN_PLATOON * PLATOONS_IN_COMPANY + 1 + i
            router.newnetif(
                self.wlan, ['%d.%d.1.%d/24' % (self.batallion_index, self.company_index, index)])
            self.routers.append(router)

        for i in xrange(PLATOONS_IN_COMPANY):
            self.connect_platoon(session, P_LOCATIONS[i])

    def connect_platoon(self, session, platoon_pos):
        platoon_index = len(self.platoons)
        platoon = Platoon(session, platoon_pos, self.wlan, self.batallion_index, self.company_index,
                          platoon_index)
        self.platoons.append(platoon)
        self.hosts.extend(platoon.hosts[1:])


class Batallion:
    def __init__(self, session, batallion_index):
        self.companies = [None]
        self.batallion_index = batallion_index
        self.twlans = []

        dist = MAX_C_DISPL / 2 + MAX_P_DISPL + MAX_P_DISPL / 10
        pos = (dist, dist, 0)
        verts = ngon_verts(COMPANIES_IN_BATALLION + 1, MAX_C_DISPL / 2)
        LOCATIONS = [(pos[0] + verts[i][0], pos[1] + verts[i][1], 0)
                     for i in xrange(COMPANIES_IN_BATALLION + 1)]
        x = LOCATIONS[0][0]
        y = LOCATIONS[0][1]

        r_verts = ngon_verts(COMPANIES_IN_BATALLION * 2, MAX_P_DISPL / 10)

        self.wlan = session.addobj(cls=pycore.nodes.WlanNode,
                                   name='uwlan%d' % (COMPANIES_IN_BATALLION + 1))
        self.wlan.setposition(x=x, y=y)
        values = list(BasicRangeModel.getdefaultvalues())
        values[0] = str(WLAN_RANGE)
        self.wlan.setmodel(BasicRangeModel, values)

        self.routers = [None]
        for i in xrange(COMPANIES_IN_BATALLION * 2):
            r_index = COMPANIES_IN_BATALLION * COMPANIES_IN_BATALLION * 2 + 1 + i
            router = session.addobj(cls=pycore.nodes.CoreNode,
                                    name='r%d' % r_index)
            router.setposition(x=x + r_verts[i][0], y=y + r_verts[i][1])
            session.services.addservicestonode(router, 'router', None, False)
            index = 1 + i
            router.newnetif(
                self.wlan, ['%d.%d.1.%d/24' % (self.batallion_index, COMPANIES_IN_BATALLION + 1, index)])
            self.routers.append(router)

        for i in xrange(1, COMPANIES_IN_BATALLION + 1):
            self.connect_company(session, LOCATIONS[i])

        top_nodes = list(self.companies) + [self]
        index = 1
        for i in xrange(1, len(top_nodes)):
            start_i = i * 2 - 1
            for j in xrange(i+1, len(top_nodes)):
                self.link(
                    session, index, top_nodes[i].routers[start_i], top_nodes[j].routers[i*2-1], top_nodes[i])
                index = index + 1
                self.link(
                    session, index, top_nodes[i].routers[start_i + 1], top_nodes[j].routers[i*2], top_nodes[j])
                index = index + 1
                start_i += 2

    def connect_company(self, session, company_pos):
        company_index = len(self.companies)
        company = Company(session, company_pos, self.batallion_index,
                          company_index)
        self.companies.append(company)

    def link(self, session, index, router1, router2, owner):
        wlan = session.addobj(cls=pycore.nodes.WlanNode,
                              name='twlan%d' % index)
        r1_pos = router1.position.get()
        r2_pos = router2.position.get()
        wlan_x = (r1_pos[0] + r2_pos[0]) / 2
        wlan_y = (r1_pos[1] + r2_pos[1]) / 2
        wlan.setposition(x=wlan_x, y=wlan_y)
        values = list(BasicRangeModel.getdefaultvalues())
        values[0] = str(WLAN_RANGE)
        wlan.setmodel(BasicRangeModel, values)
        owner.twlans.append(wlan)
        router1.newnetif(
            wlan, ['%d.%d.9.1/24' % (self.batallion_index, index)])
        router2.newnetif(
            wlan, ['%d.%d.9.2/24' % (self.batallion_index, index)])


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
            if elapsed >= config[0].start_time:
                while elapsed > config[0].end_time:
                    del config[0]

                current = config[0]

                lerp_amount = (elapsed - current.start_time) \
                    / (current.end_time - current.start_time)
                delta = (current.end_pos[0] - current.start_pos[0],
                         current.end_pos[1] - current.start_pos[1], 0)
                new_x = max(min(current.start_pos[0] +
                                lerp_amount * delta[0], WIDTH), 0)
                new_y = max(min(current.start_pos[1] +
                                lerp_amount * delta[1], HEIGHT), 0)
                current.node.setposition(new_x, new_y, 0)
                msg = current.node.tonodemsg(flags=0)
                session.broadcastraw(None, msg)
                session.sdt.updatenode(
                    current.node.objid, flags=0, x=new_x, y=new_y, z=0)

                if elapsed + 0.001 * refresh_ms > current.end_time:
                    del config[0]

        elapsed += 0.001 * refresh_ms
        time.sleep(0.001 * refresh_ms)


def generate_configs(batallion):
    configs = []

    def pos_to_tuple(pos):
        coords = pos.split()
        return (int(coords[0]), int(coords[1]), 0)

    with open('/home/linth1/core-scripts/batallion_movement.csv') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        index = 0
        for row in csv_reader:
            if index == 0:
                times = row
            else:
                octets = row[0].split('.')
                if len(octets) == 4:
                    node = batallion.companies[int(
                        octets[1])].hosts[int(octets[3])]
                    if not hasattr(node, 'config_index'):
                        setattr(node, 'config_index', len(configs))
                        configs.append([])
                    else:
                        configs[node.config_index] = []

                    last_wp_index = None
                    for i in xrange(1, len(row)):
                        if row[i]:
                            if (last_wp_index is None):
                                if (i != 1):
                                    configs[node.config_index].append(MovementConfig(
                                        node, node.position.get(), pos_to_tuple(row[i]), 0, int(times[i])))
                            else:
                                configs[node.config_index].append(MovementConfig(node, pos_to_tuple(
                                    row[last_wp_index]), pos_to_tuple(row[i]), int(times[last_wp_index]), int(times[i])))
                            last_wp_index = i
                elif len(octets) == 2:
                    company = batallion.companies[int(octets[1])]
                    company.waypoints = []
                    company.wp_times = []
                    for i in xrange(1, len(row)):
                        if row[i]:
                            company.waypoints.append(pos_to_tuple(row[i]))
                            company.wp_times.append(int(times[i]))
                    configs = generate_random_configs(configs, company, True)
                elif len(octets) == 1:
                    batallion.waypoints = []
                    batallion.wp_times = []
                    for i in xrange(1, len(row)):
                        if row[i]:
                            batallion.waypoints.append(
                                pos_to_tuple(row[i]))
                            batallion.wp_times.append(int(times[i]))
                    configs = generate_random_configs(configs, batallion)

            index += 1
    print configs
    return configs


def generate_random_configs(configs, unit, reset=False):
    HOST_LOCS = ngon_verts(HOSTS_IN_PLATOON, MAX_P_DISPL / 10)
    ROUTER_LOCS = ngon_verts(COMPANIES_IN_BATALLION * 2, MAX_P_DISPL / 10)

    margin = MAX_C_DISPL + MAX_P_DISPL + MAX_P_DISPL / 10

    def add_config(node, config):
        if not hasattr(node, 'config_index'):
            setattr(node, 'config_index', len(configs))
            configs.append([])
        configs[node.config_index].append(config)

    if isinstance(unit, Batallion):
        batallion = unit
        companies = batallion.companies[1:]

        if not hasattr(batallion, 'waypoints'):
            b_start_pos = batallion.wlan.position.get()
            b_end_x = randint(WIDTH - margin, WIDTH)
            b_end_y = randint(HEIGHT - margin, HEIGHT)
            b_end_pos = (b_end_x, b_end_y, 0)

            b.waypoints = [b_start_pos, b_end_pos]
            b.wp_times = [0, TIME]

        for i in xrange(1, len(batallion.waypoints)):
            b_wp = batallion.waypoints[i]
            b_wp_time = batallion.wp_times[i]
            last_b_wp = batallion.waypoints[i - 1]
            last_b_wp_time = batallion.wp_times[i - 1]

            add_config(batallion.wlan, MovementConfig(batallion.wlan,
                                                      last_b_wp, b_wp, last_b_wp_time, b_wp_time))
            for i in xrange(2 * COMPANIES_IN_BATALLION):
                b_router = batallion.routers[i + 1]
                add_config(b_router, MovementConfig(b_router, (last_b_wp[0] + ROUTER_LOCS[i][0], last_b_wp[1] + ROUTER_LOCS[i][1], 0), (
                    b_wp[0] + ROUTER_LOCS[i][0], b_wp[1] + ROUTER_LOCS[i][1], 0), last_b_wp_time, b_wp_time))

            for twlan in batallion.twlans:
                add_config(twlan, MovementConfig(
                    twlan, last_b_wp, b_wp, last_b_wp_time, b_wp_time))

    elif isinstance(unit, Company):
        companies = [unit]

    for company in companies:
        if reset:
            for platoon in company.platoons[1:]:
                if hasattr(platoon, 'start_pos'):
                    del platoon.start_pos
                for host in platoon.hosts[1:]:
                    configs[host.config_index] = []
            configs[company.wlan.config_index] = []
            for router in company.routers[1:]:
                configs[router.config_index] = []
            for twlan in company.twlans:
                configs[twlan.config_index] = []

        c_start_time = 0
        if not hasattr(company, 'waypoints'):
            company.waypoints = []
            company.wp_times = []

            for i in xrange(len(batallion.waypoints)):
                b_wp = batallion.waypoints[i]
                b_wp_time = batallion.wp_times[i]

                if i <= 0 or b_wp[0] != batallion.waypoints[i-1][0] or b_wp[1] != batallion.waypoints[i-1][1]:
                    c_offset = [randint(-MAX_C_DISPL, MAX_C_DISPL),
                                randint(-MAX_C_DISPL, MAX_C_DISPL)]

                c_wp = (b_wp[0] + c_offset[0], b_wp[1] + c_offset[1], 0)
                company.waypoints.append(c_wp)
                company.wp_times.append(b_wp_time)

        for i in xrange(1, len(company.waypoints)):
            c_wp = company.waypoints[i]
            c_wp_time = company.wp_times[i]
            last_c_wp = company.waypoints[i - 1]
            last_c_wp_time = company.wp_times[i - 1]

            p_delta = (c_wp[0] - last_c_wp[0],
                       c_wp[1] - last_c_wp[1], 0)

            for platoon in company.platoons[1:]:
                p_start_time = last_c_wp_time
                p_offset = [randint(-MAX_P_DISPL, MAX_P_DISPL),
                            randint(-MAX_P_DISPL, MAX_P_DISPL)]
                if not hasattr(platoon, 'start_pos'):
                    platoon.start_pos = (
                        last_c_wp[0] + p_offset[0], last_c_wp[1] + p_offset[1], 0)

                while p_start_time < c_wp_time:
                    p_end_time = min(
                        randint(p_start_time + 1, p_start_time + P_MAX_TIME_BT_WP), c_wp_time)
                    percentage = float(p_end_time -
                                  last_c_wp_time) / (c_wp_time - last_c_wp_time)
                    p_offset = [randint(-MAX_P_DISPL, MAX_P_DISPL),
                                randint(-MAX_P_DISPL, MAX_P_DISPL)]
                    p_end_pos = (last_c_wp[0] + (percentage * p_delta[0]) + p_offset[0],
                                 last_c_wp[1] + (percentage * p_delta[1]) + p_offset[1], 0)
                    for i in xrange(HOSTS_IN_PLATOON):
                        host = platoon.hosts[i + 1]
                        add_config(host, MovementConfig(host, (platoon.start_pos[0] + HOST_LOCS[i][0], platoon.start_pos[1] + HOST_LOCS[i][1], 0), (
                            p_end_pos[0] + HOST_LOCS[i][0], p_end_pos[1] + HOST_LOCS[i][1], 0), p_start_time, p_end_time))

                    p_start_time = p_end_time
                    platoon.start_pos = p_end_pos

            add_config(company.wlan, MovementConfig(
                company.wlan, last_c_wp, c_wp, last_c_wp_time, c_wp_time))

            for i in xrange(2 * COMPANIES_IN_BATALLION):
                c_router = company.routers[i + 1]
                add_config(c_router, MovementConfig(c_router, (last_c_wp[0] + ROUTER_LOCS[i][0], last_c_wp[1] + ROUTER_LOCS[i][1], 0), (
                    c_wp[0] + ROUTER_LOCS[i][0], c_wp[1] + ROUTER_LOCS[i][1], 0), last_c_wp_time, c_wp_time))

            for twlan in company.twlans:
                add_config(twlan, MovementConfig(
                    twlan, last_c_wp, c_wp, last_c_wp_time, c_wp_time))

    return configs


def main():

    start = datetime.datetime.now()

    session = pycore.Session(persistent=True)
    if 'server' in globals():
        server.addsession(session)

    batallion = Batallion(session, 1)

    num_nodes = COMPANIES_IN_BATALLION * (HOSTS_IN_PLATOON * PLATOONS_IN_COMPANY + 2 * COMPANIES_IN_BATALLION + 1) + \
        2 * COMPANIES_IN_BATALLION + 1 + \
        (COMPANIES_IN_BATALLION + 1) * COMPANIES_IN_BATALLION
    print 'Finished creating %d nodes.' % num_nodes

    if MOVEMENT:
        thread = threading.Thread(target=movement_thread,
                                  args=(generate_configs(batallion), session, REFRESH_MS,))
        thread.start()
        thread.join()

    session.node_count = num_nodes
    session.instantiate()

    print "elapsed time: %s" % (datetime.datetime.now() - start)


if __name__ == '__main__' or __name__ == '__builtin__':
    main()
