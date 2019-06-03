import random
import networkx as nx
import anti_sybil.graphs as graphs
import anti_sybil.algorithms as algorithms
from anti_sybil.utils import *
from arango import ArangoClient
from db_config import *

def update(nodes_graph, groups_graph):
    client = ArangoClient()
    db = client.db(DB_NAME, username=DB_USER, password=DB_PASS)
    for node in nodes_graph.nodes:
        db['users'].update({'_key': node.name, 'score': node.rank})
    for group in groups_graph.nodes:
        db['groups'].update({'_key': group.name, 'score': group.rank,
                             'raw_rank': group.raw_rank, 'degree': group.degree})

def load():
    client = ArangoClient()
    db = client.db(DB_NAME, username=DB_USER, password=DB_PASS)
    users = db.collection('users')
    groups = db.collection('groups')
    connections = db.collection('connections')
    usersInGroups = db.collection('usersInGroups')
    user_groups = {}
    seed_groups = set([group['_key']
                       for group in groups if group.get('seed', None)])
    for user_group in usersInGroups:
        if not user_group['_from'].replace('users/', '') in user_groups:
            user_groups[user_group['_from'].replace('users/', '')] = set()
        user_groups[user_group['_from'].replace(
            'users/', '')].add(user_group['_to'].replace('groups/', ''))
    users_dic = {}
    for user in users:
        cur_user_groups = user_groups.get(user['_key'])
        user_type = 'Seed' if cur_user_groups and (cur_user_groups & seed_groups) else 'Honest'
        users_dic[user['_key']] = graphs.node.Node(
            user['_key'], user_type, cur_user_groups, user['score'])
    edges = [(users_dic[connection['_from'].replace('users/', '')], users_dic[connection['_to'].replace('users/', '')])
             for connection in connections]
    graph = nx.Graph()
    graph.add_edges_from([(edge[0], edge[1]) for edge in edges])
    return graph

def stupid_sybil_border(graph):
    reset_ranks(graph)
    ranker = algorithms.SybilGroupRank(graph)
    ranker.rank()
    attacker = max(graph.nodes, key=lambda node: node.rank)
    attacker.groups.add('stupid_sybil')
    sybil1 = graphs.node.Node('stupid_sybil_1', 'Sybil', set(['stupid_sybil']))
    sybil2 = graphs.node.Node('stupid_sybil_2', 'Sybil', set(['stupid_sybil']))
    graph.add_edge(attacker, sybil1)
    graph.add_edge(attacker, sybil2)
    reset_ranks(graph)
    ranker = algorithms.SybilGroupRank(graph)
    ranker.rank()
    border = max(sybil1.raw_rank, sybil2.raw_rank)
    graph.remove_nodes_from([sybil1, sybil2])
    attacker.groups.remove('stupid_sybil')
    reset_ranks(graph)
    return border

if __name__ == '__main__':
    graph = load()
    border = stupid_sybil_border(graph)
    raw_ranks = [node.raw_rank for node in graph.nodes]
    print('''stupid border: {}
max: {}
min: {}
avg: {}'''.format(border, max(raw_ranks), min(raw_ranks), sum(raw_ranks) / len(raw_ranks)))
    reset_ranks(graph)
    ranker = algorithms.SybilGroupRank(graph, {
        'stupid_sybil_border': border
    })
    ranker.rank()
    draw_graph(ranker.graph, 'nodes.html')
    draw_graph(ranker.group_graph, 'groups.html')
    update(ranker.graph, ranker.group_graph)