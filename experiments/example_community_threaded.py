"""An example community (FloodCommunity) to both show
how Dispersy works and how VisualDispersy works.
Credit for the original tutorial Community goes to Boudewijn Schoon.
"""

import logging
import struct
import sys
import time
import string
import os.path

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

    """A simple community to exemplify Dispersy behavior.
    """

    def __init__(self, dispersy, master_member, my_member):
        """Callback for when Dispersy initializes this community.
            Note that this function signature is a Dispersy requirement.
        """
        super(
            FloodCommunity,
            self).__init__(
                dispersy,
                master_member,
         my_member)
        self.message_received = 0

    def initiate_conversions(self):
        """Tell Dispersy what wire conversion handlers we have.
        """
        return [DefaultConversion(self), FloodConversion(self)]

    @property
    def dispersy_auto_download_master_member(self):
        """Do not automatically download our (bogus) master member.
        """
        return False

    @property
    def dispersy_enable_fast_candidate_walker(self):
        return True

    def initiate_meta_messages(self):
        """>EXTEND< the current meta messages with our custom Flood type.
        """
        messages = super(FloodCommunity, self).initiate_meta_messages()
        ourmessages = [Message(self,
                               u"flood",
                               # Unique identifier
                               MemberAuthentication(
                               encoding="sha1"),
                               # Member identifier hash type
                               PublicResolution(),
                               # All members can add messages
                               FullSyncDistribution(
                               enable_sequence_number=False,
                               synchronization_direction=u"ASC",
                               priority=255),
                               # Synchronize without sequence number, delivering messages with the lowest
                               # (Lamport) global time first and the highest priority
                               CommunityDestination(
                               node_count=10),
                               # Push to >AT MOST< 10 other nodes initially
                               FloodPayload(),
                               # The object to actually carry our payload
                               self.check_flood,
                               # Callback to validate a received message
                               self.on_flood,
                               # Callback to actually handle a validated
                               # message
                               batch=BatchConfiguration(0.0))]  # Amount of time (seconds) to save up messages before handling them
        messages.extend(ourmessages)
        return messages

    def create_flood(self, count):
        """Dump some messages into the Community overlay.
        """
        self.start_flood_time = time.time()
        if count <= 0:
            return
        # Retrieve the meta object we defined in initiate_meta_messages()
        meta = self.get_meta_message(u"flood")
        # Instantiate the message
        messages = [meta.impl(authentication=(self.my_member,),  # This client signs this message
                              # distribution=(self.claim_global_time(),meta.distribution.claim_sequence_number()),
                              # # When you enable sequence numbers (see
                              # initiate_meta_messages)
                              distribution=(
                              self.claim_global_time(),
        ),
            # Without sequence numbers you just need our
                              # value of the Lamport clock
                              payload=("flood #%d" % (i + (self.peerid - 1) * count),))  # Some arbitrary message contents
            for i
                    in xrange(count)]
        # Spread this message into the network (including to ourselves)
        self.dispersy.store_update_forward(messages, True, True, True)

    def check_flood(self, messages):
        """Callback to verify the contents of the messages received.
        """
        for message in messages:
            # We don't actually check them, just forward them
            # Otherwise check out DropPacket and the like in dispersy.message
            yield message

    def on_flood(self, messages):
        """Callback for when validated messages are received.
        """
        self.message_received += len(messages)
        # Report to Visual Dispersy
        self.vz_report_target(
            "messages",
            self.message_received,
            self.total_message_count)
        if self.message_received == self.total_message_count:
            # Wait for the experiment to end IN A THREAD
            # If you don't do this YOU WILL BLOCK DISPERSY COMPLETELY
            reactor.callInThread(self.wait_for_end)

    def wait_for_end(self):
        """Busy wait for the experiment to end
        """
        self.vz_wait_for_experiment_end()
        self.dispersy.stop()


class FloodPayload(Payload):

    """The data container for FloodCommunity communications.
    """
    class Implementation(Payload.Implementation):

        def __init__(self, meta, data):
            super(FloodPayload.Implementation, self).__init__(meta)
            self.data = data


class FloodConversion(BinaryConversion):

    """Convert the payload into binary data (/a string) which can be
        sent over the internet.
    """

    def __init__(self, community):
        """Initialize the new Conversion object
        """
        super(FloodConversion, self).__init__(community, "\x01")
              # Use community version 1 (only communicates with other version
              # 1's)
        self.define_meta_message(
            chr(1),
            community.get_meta_message(u"flood"),
            self._encode_flood,
            self._decode_flood)  # Our only message type is assigned id 1 (byte), with encode and decode callbacks

    def _encode_flood(self, message):
        """The encode callback to convert a Message into a binary representation (string).
        """
        return struct.pack("!L", len(message.payload.data)), message.payload.data

    def _decode_flood(self, placeholder, offset, data):
        """Given a binary representation of our payload
            convert it back to a message.
        """
        if len(data) < offset + 4:
            raise DropPacket("Insufficient packet size")
        data_length, = struct.unpack_from("!L", data, offset)
        offset += 4

        if len(data) < offset + data_length:
            raise DropPacket("Insufficient packet size")
        data_payload = data[offset:offset + data_length]
        offset += data_length

        return offset, placeholder.meta.payload.implement(data_payload)


def join_flood_overlay(
    dispersy,
     masterkey,
     peerid,
     totalpeers,
     new_message_count,
     total_message_count):
    """Join our custom FloodCommunity.
    """
    
    time.sleep(5.0)

    # Use our bogus master member
    master_member = dispersy.get_member(public_key=masterkey)
    # Register our client with Dispersy
    my_member = dispersy.get_new_member()
    # Register our community with Dispersy
    community = FloodCommunity.init_community(
        dispersy, master_member, my_member)
    # Initialize our custom community, because we can't change the constructor
    community.total_message_count = total_message_count
    community.peerid = peerid
    community.totalpeers = totalpeers
    # Report to Visual Dispersy
    community.vz_report_target("messages", 0, total_message_count)

    print "%d] Joined community" % (dispersy.lan_address[1])

    # Allow the Community members some time to find each other.
    while len(list(community.dispersy_yield_verified_candidates())) < totalpeers:
        time.sleep(1.0)

    print "%d] Flooding community" % (dispersy.lan_address[1])

    # Call our message creation function to share a certain amount
    # of messages with the Community.
    community.create_flood(new_message_count)


def generateMasterkey():
    """Generate an M2Crypto Elliptic Curve key.
    """
    membuffer = BIO.MemoryBuffer()
    keypair = EC.gen_params(EC.NID_sect233k1)
    keypair.gen_key()
    keypair.save_pub_key_bio(membuffer)
    rawpubkey = membuffer.read()
    membuffer.reset()
    fpubkey = rawpubkey[27:]
    fpubkey = fpubkey[:string.find(fpubkey, '-')]
    return fpubkey  # BASE64 ENCODED


def establishMasterkey(peerid):
    """Get the master key for this community.
        This is stored in the file 'generated_master_key.key'.
        Peerid 1 is responsible for making sure this file exists.
    """
    if peerid == 1:
        # Peerid 1 makes sure the key file exists
        if not os.path.isfile('generated_master_key.key'):
            f = open('generated_master_key.key', 'w')
            f.write(generateMasterkey())
            f.close()
    else:
        # All other peers simply wait for the keyfile to exist
        # [And pray peer 1 did not crash]
        while not os.path.isfile('generated_master_key.key'):
            time.sleep(0.5)

    keyfile = open('generated_master_key.key', 'r')
    masterkey = keyfile.read().decode("BASE64")
    keyfile.close()
    return masterkey


def stopOnDispersy(dispersy, reactor):
    """Exit when Dispersy closes.
    """
    time.sleep(20.0)
    while dispersy.running:
        time.sleep(10.0)
    reactor.stop()


def main(
    peerid,
     totalpeers,
     new_message_count,
     total_message_count,
     vz_server_port):
    """VisualDispersy will call this function with:
        - peerid: [1~totalpeers] our id
        - totalpeers: the total amount of peers in our experiment
        - new_message_count: the amount of messages we are supposed to share
        - total_message_count: the total amount of messages we are supposed to receive (including our own)
        - vz_server_port: the server port we need to connect to for VisualDispersy
    """
    # Get the master key
    masterkey = establishMasterkey(peerid)

    # Make an endpoint (starting at port 10000, incrementing until we can open)
    endpoint = StandaloneEndpoint(10000)
    # Create a VisualDispersy instance for the endpoint and store the SQLite 3
    # database in RAM
    dispersy = VisualDispersy(endpoint, u".", u":memory:")
    # Initialize the VisualDispersy server connection
    dispersy.vz_init_server_connection(vz_server_port)

    # Start Dispersy in a thread (it blocks)
    reactor.callInThread(dispersy.start, True)
    # Add an observer to do a clean exit when Dispersy is closed
    reactor.callInThread(stopOnDispersy, dispersy, reactor)
    # After 20 seconds, start the experiment
    reactor.callInThread(
        join_flood_overlay,
     dispersy,
     masterkey,
     peerid,
     totalpeers,
     new_message_count,
     total_message_count)
    reactor.run()
