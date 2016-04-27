import logging
import struct
import sys
import time
import string
import os.path
import random

# Void all Dispersy log messages
logging.basicConfig(level=logging.CRITICAL)
logging.getLogger().propagate = False

from M2Crypto import EC, BIO
from twisted.internet import reactor, threads
from dispersy.authentication import MemberAuthentication
from dispersy.community import Community
from dispersy.conversion import DefaultConversion, BinaryConversion
from dispersy.destination import CommunityDestination
from dispersy.dispersy import Dispersy
from dispersy.distribution import FullSyncDistribution
from dispersy.endpoint import StandaloneEndpoint
from dispersy.member import DummyMember
from dispersy.message import Message, DropPacket, DropMessage, BatchConfiguration
from dispersy.payload import Payload
from dispersy.resolution import PublicResolution

from dispersyviz.visualdispersy import VisualDispersy, VisualCommunity

class FloodCommunity(VisualCommunity):
    def __init__(self, dispersy, master_member, my_member):
        super(FloodCommunity, self).__init__(dispersy, master_member, my_member)
        self.message_received = 0

    def initiate_conversions(self):
        return [DefaultConversion(self), FloodConversion(self)]

    @property
    def dispersy_auto_download_master_member(self):
        return False

    def initiate_meta_messages(self):
        messages = super(FloodCommunity, self).initiate_meta_messages()
        ourmessages = [Message(self,
                        u"flood",
                        MemberAuthentication(encoding="sha1"),
                        PublicResolution(),
                        FullSyncDistribution(enable_sequence_number=False, synchronization_direction=u"ASC", priority=255),
                        CommunityDestination(node_count=10),
                        FloodPayload(),
                        self.check_flood,
                        self.on_flood,
                        batch=BatchConfiguration(3.0+random.random()))]
        messages.extend(ourmessages)
        return messages

    def create_flood(self, count):
        self.start_flood_time = time.time()
        if count <= 0:
            return
        meta = self.get_meta_message(u"flood")
        messages = [meta.impl(authentication=(self.my_member,),
                              #distribution=(self.claim_global_time(),meta.distribution.claim_sequence_number()),
                              distribution=(self.claim_global_time(),),
                              payload=("flood #%d" % (i+(self.peerid-1)*count),))
                    for i
                    in xrange(count)] 
        self.dispersy.store_update_forward(messages, True, True, True)

    def check_flood(self, messages):
        for message in messages:
            yield message

    def on_flood(self, messages):
        self.message_received += len(messages)
        self.vz_report_target("messages", self.message_received, self.total_message_count)
        if self.message_received == self.total_message_count:
            reactor.callInThread(self.wait_for_end)

    def wait_for_end(self):
        self.vz_wait_for_experiment_end()
        self.dispersy.stop()

class FloodPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, data):
            super(FloodPayload.Implementation, self).__init__(meta)
            self.data = data

class FloodConversion(BinaryConversion):
    def __init__(self, community):
        super(FloodConversion, self).__init__(community, "\x01")
        self.define_meta_message(chr(1), community.get_meta_message(u"flood"), self._encode_flood, self._decode_flood)

    def _encode_flood(self, message):
        return struct.pack("!L", len(message.payload.data)), message.payload.data

    def _decode_flood(self, placeholder, offset, data):
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        offset += data_length

        return offset, placeholder.meta.payload.implement(data_payload)

def join_flood_overlay(dispersy, masterkey, peerid, totalpeers, new_message_count, total_message_count):
    master_member = dispersy.get_member(public_key=masterkey)
    my_member = dispersy.get_new_member()
    community = FloodCommunity.init_community(dispersy, master_member, my_member)
    community.total_message_count = total_message_count
    community.peerid = peerid
    community.totalpeers = totalpeers

    print "%d] Joined community" % (dispersy.lan_address[1])

    time.sleep(10.0)

    print "%d] Flooding community" % (dispersy.lan_address[1])

    community.create_flood(new_message_count)

def generateMasterkey():
    membuffer = BIO.MemoryBuffer()
    keypair = EC.gen_params(EC.NID_sect233k1)
    keypair.gen_key()
    keypair.save_pub_key_bio(membuffer)
    rawpubkey = membuffer.read()
    membuffer.reset()
    fpubkey = rawpubkey[27:]
    fpubkey = fpubkey[:string.find(fpubkey,'-')]
    return fpubkey # BASE64 ENCODED

def establishMasterkey(peerid):
    if peerid == 1:
        if not os.path.isfile('generated_master_key.key'):
            f = open('generated_master_key.key', 'w')
            f.write(generateMasterkey())
            f.close()
    else:
        while not os.path.isfile('generated_master_key.key'):
            time.sleep(0.5)

    keyfile = open('generated_master_key.key', 'r')
    masterkey = keyfile.read().decode("BASE64")
    keyfile.close()
    return masterkey

def stopOnDispersy(dispersy, reactor):
    time.sleep(20.0)
    while dispersy.running:
        time.sleep(10.0)
    reactor.stop()

def main(peerid, totalpeers, new_message_count, total_message_count, vz_server_port):
    masterkey = establishMasterkey(peerid)

    endpoint = StandaloneEndpoint(10000)
    dispersy = VisualDispersy(endpoint, u".", u":memory:")
    dispersy.vz_init_server_connection(vz_server_port)

    reactor.callInThread(dispersy.start, True)
    reactor.callInThread(stopOnDispersy, dispersy, reactor)
    reactor.callLater(20.0, join_flood_overlay, dispersy, masterkey, peerid, totalpeers, new_message_count, total_message_count)
    reactor.run()
