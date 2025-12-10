import grpc
import service_pb2, service_pb2_grpc

if __name__ == "__main__":
    channel = grpc.insecure_channel("localhost:50051")
    stub = service_pb2_grpc.AIServiceStub(channel)
    for answer in stub.QA(service_pb2.Question(question="What is the capital of France?")):
        print(f"[{answer.sequence}] {answer.answer}")