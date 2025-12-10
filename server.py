import grpc
import time
import random
from concurrent import futures
import service_pb2, service_pb2_grpc

class AIServiceServicer(service_pb2_grpc.AIServiceServicer):
    def QA(self, request, context):
        for i in range(10):
            yield service_pb2.Answer(answer=f"Answering question {request.question} - {i}", sequence=i)
            time.sleep(random.random())

if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service_pb2_grpc.add_AIServiceServicer_to_server(AIServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()