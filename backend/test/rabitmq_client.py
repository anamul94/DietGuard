import pika

def on_message(channel, method_frame, header_frame, body):
  print(f"Received message: {body.decode()}")

def main():
  connection = pika.BlockingConnection(pika.ConnectionParameters(host='15.207.68.194', port=5672))
  channel = connection.channel()

  queue_name = 'event_queue'
  channel.queue_declare(queue=queue_name, durable=True)

  channel.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=True)

  print('Waiting for events. To exit press CTRL+C')
  try:
    channel.start_consuming()
  except KeyboardInterrupt:
    channel.stop_consuming()
  finally:
    connection.close()

if __name__ == '__main__':
  main()