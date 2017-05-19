#!/bin/bash

# NOTE: using stable/newton to stay compatible with it
RELEASE=${RELEASE:-newton}
CONSTRAINTS=https://git.openstack.org/cgit/openstack/requirements/plain/upper-constraints.txt?h=stable/$RELEASE

pip uninstall ironic -y || true
pip install -U -c $CONSTRAINTS $@
pip install -U -c $CONSTRAINTS -r https://git.openstack.org/cgit/openstack/ironic/tree/requirements.txt?h=stable/$RELEASE
pip install git+git://git.openstack.org/openstack/ironic@stable/$RELEASE#egg=ironic
