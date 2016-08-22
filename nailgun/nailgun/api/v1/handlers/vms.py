# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import traceback

import six
import web

from nailgun.api.v1.handlers.base import BaseHandler
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import validate
from nailgun.api.v1.validators import node as validators

from nailgun.logger import logger

from nailgun import objects

from nailgun.orchestrator import orchestrator_graph
from nailgun.task import manager


class SpawnVmsHandler(BaseHandler):
    """Handler for provision and spawn vms on virt nodes."""

    task_manager = manager.SpawnVMsTaskManager
    validator = validators.DeploySelectedNodesValidator

    def get_tasks(self, cluster, graph_type):
        """Get deployment tasks for VMs spawning.

        :param cluster: models.Cluster instance
        :type cluster: models.Cluster
        :param graph_type: Deployment graph type
        :type graph_type: basestring
        :returns: list of tasks ids
        :rtype: list[basestring]
        """
        tasks = objects.Cluster.get_deployment_tasks(cluster, graph_type)
        graph = orchestrator_graph.GraphSolver()
        graph.add_tasks(tasks)
        subgraph = graph.find_subgraph(end='generate_vms')
        return [task['id'] for task in subgraph.topology]

    def get_nodes(self, cluster):
        return objects.Cluster.get_nodes_to_spawn_vms(cluster)

    def handle_task(self, cluster, **kwargs):
        nodes = self.get_nodes(cluster)
        if nodes:
            try:
                task_manager = self.task_manager(cluster_id=cluster.id)
                task = task_manager.execute(nodes_to_provision_deploy=nodes,
                                            **kwargs)
            except Exception as exc:
                logger.warn(
                    u'Cannot execute %s task nodes: %s',
                    task_manager.__class__.__name__, traceback.format_exc())
                raise self.http(400, six.text_type(exc))
            self.raise_task(task)
        else:
            raise self.http(400, "No VMs to spawn")

    @handle_errors
    @validate
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.

        :http: * 200 (task successfully executed)
               * 202 (task scheduled for execution)
               * 400 (data validation failed)
               * 404 (cluster not found in db)
        """
        graph_type = web.input(graph_type=None).graph_type or None
        cluster = self.get_object_or_404(objects.Cluster, cluster_id)
        data = self.get_tasks(cluster, graph_type)
        return self.handle_task(cluster, deployment_tasks=data,
                                graph_type=graph_type)


class NodeVMsHandler(BaseHandler):
    """Node vms handler"""

    validator = validators.NodeVMsValidator

    @handle_errors
    @validate
    @serialize
    def GET(self, node_id):
        """:returns: JSONized node vms_conf.

        :http: * 200 (OK)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        node_vms = node.vms_conf
        return {"vms_conf": node_vms}

    @handle_errors
    @validate
    @serialize
    def PUT(self, node_id):
        """:returns: JSONized node vms_conf.

        :http: * 200 (OK)
               * 400 (invalid vmsdata specified)
               * 404 (node not found in db)
        """
        node = self.get_object_or_404(objects.Node, node_id)
        data = self.checked_data()

        node.vms_conf = data.get("vms_conf")
        return {"vms_conf": node.vms_conf}
