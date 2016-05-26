#    Copyright 2016 Mirantis, Inc.
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

from devops.helpers import helpers as devops_helpers
from fuelweb_test import logger
from proboscis import asserts
import requests

from stacklight_tests import base_test
from stacklight_tests.influxdb_grafana.grafana_ui import api as ui_api
from stacklight_tests.influxdb_grafana import plugin_settings


class InfluxdbPluginApi(base_test.PluginApi):
    def get_plugin_settings(self):
        return plugin_settings

    def prepare_plugin(self):
        self.helpers.prepare_plugin(self.settings.plugin_path)

    def activate_plugin(self, options=None):
        if options is None:
            options = self.settings.default_options
        self.helpers.activate_plugin(
            self.settings.name, self.settings.version, options)

    def get_plugin_vip(self):
        return self.helpers.get_plugin_vip(self.settings.vip_name)

    def get_grafana_url(self, resource=''):
        return "http://{0}:8000/{1}".format(self.get_plugin_vip(), resource)

    def get_influxdb_url(self, resource=''):
        return "http://{0}:8086/{1}".format(self.get_plugin_vip(), resource)

    def do_influxdb_query(self,
                          query,
                          db=plugin_settings.influxdb_db_name,
                          user=plugin_settings.influxdb_user,
                          password=plugin_settings.influxdb_pass,
                          expected_code=200):
        return self.checkers.check_http_get_response(
            url=self.get_influxdb_url('query'),
            expected_code=expected_code,
            params={"db": db, "u": user, "p": password, "q": query})

    def check_plugin_online(self):
        logger.info("Check that the InfluxDB server replies to ping requests")
        self.checkers.check_http_get_response(
            url=self.get_influxdb_url('ping'),
            expected_code=204)

        logger.info("Check that the InfluxDB API requires authentication")
        self.do_influxdb_query("show measurements",
                               user=plugin_settings.influxdb_user,
                               password='rogue', expected_code=401)

        logger.info("Check that the InfluxDB user is authorized")
        self.do_influxdb_query("show measurements")

        logger.info("Check that the InfluxDB user doesn't have admin rights")
        self.do_influxdb_query("show servers", expected_code=401)

        logger.info("Check that the InfluxDB root user has admin rights")
        self.do_influxdb_query("show servers",
                               user=plugin_settings.influxdb_rootuser,
                               password=plugin_settings.influxdb_rootpass)

        logger.info("Check that the Grafana UI server is running")
        self.checkers.check_http_get_response(
            self.get_grafana_url('login'))

        logger.info("Check that the Grafana user is authorized")
        self.checkers.check_http_get_response(
            self.get_grafana_url('api/org'),
            auth=(plugin_settings.grafana_user, plugin_settings.grafana_pass))

        logger.info("Check that the Grafana API requires authentication")
        self.checkers.check_http_get_response(
            self.get_grafana_url('api/org'),
            auth=(plugin_settings.grafana_user, 'rogue'), expected_code=401)

    def check_influxdb_nodes_count(self, count=1):
        logger.debug('Check the number of InfluxDB servers')
        response = self.do_influxdb_query(
            "show servers",
            user=self.settings.influxdb_rootuser,
            password=self.settings.influxdb_rootpass)

        nodes_count_responsed = len(
            response.json()["results"][0]["series"][0]["values"])

        msg = "Expected {0} InfluxDB nodes, got {}".format(
            count, nodes_count_responsed)
        asserts.assert_equal(count, nodes_count_responsed, msg)

    def wait_plugin_online(self, timeout=5 * 60):
        def check_availability():
            try:
                self.check_plugin_online()
                return True
            except (AssertionError, requests.ConnectionError):
                return False

        logger.info('Wait a plugin become online')
        msg = "Plugin has not become online after waiting period"
        devops_helpers.wait(
            check_availability, timeout=timeout, timeout_msg=msg)

    def uninstall_plugin(self):
        return self.helpers.uninstall_plugin(self.settings.name,
                                             self.settings.version)

    def check_uninstall_failure(self):
        return self.helpers.check_plugin_cannot_be_uninstalled(
            self.settings.name, self.settings.version)

    def check_grafana_dashboards(self):
        grafana_url = self.get_grafana_url()
        ui_api.check_grafana_dashboards(grafana_url)
