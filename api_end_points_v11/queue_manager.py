#!/usr/bin/env python
import pika
import uuid
from pika.adapters import SelectConnection


class DataProvisionClient(object):
    def __init__(self, queue, request):
        self.queue = queue
        self.response = None
        self.channel = None
        self.request = request
        self.corrId = str(uuid.uuid4())
        self.callBackQueue = None
        self.connection = None
        parameters = pika.ConnectionParameters(host='127.0.0.1')
        self.connection = SelectConnection(parameters,
                                           self.on_response_connected)
        self.connection.ioloop.start()

    def on_response(self, ch, method, props, body):
        if self.corrId == props.correlation_id:
            self.response = body
            self.connection.close()
            self.connection.ioloop.start()

    def on_response_connected(self, connection):
        print('connected ..')
        self.connection = connection
        self.connection.channel(self.on_channel_open)

    def on_response_channel_open(self, channel):
        self.responseChannel = channel
        result = self.responseChannel.queue_declare(exclusive=True,
                                                    callback=self.on_response_queue_declared)

    def on_connected(self, connection):
        self.connection = connection
        self.connection.channel(self.on_channel_open)

    def on_channel_open(self, channel):
        print('channel opened')
        self.channel = channel
        self.channel.queue_declare(queue=self.queue,
                                   durable=True,
                                   exclusive=False,
                                   auto_delete=False,
                                   callback=self.on_queue_declared)

    def on_queue_declared(self, frame):
        self.channel.basic_publish(exchange='',
                                   routing_key=self.queue,
                                   properties=pika.BasicProperties(),
                                   body=str(self.request))
        self.connection.close()
        print('message delivered')
