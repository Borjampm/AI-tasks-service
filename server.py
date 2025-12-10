import grpc
from concurrent import futures
import service_pb2, service_pb2_grpc

class MyServiceServicer(service_pb2_grpc.MyServiceServicer):
    def DoSomething(self, request, context):
        if request.data == "Hello":
            return service_pb2.Response(result="Hello, World!")
        else:
            print(f"Invalid request: {request.data}")
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid request")

if __name__ == "__main__":
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service_pb2_grpc.add_MyServiceServicer_to_server(MyServiceServicer(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    server.wait_for_termination()