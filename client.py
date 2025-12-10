import grpc
import service_pb2, service_pb2_grpc

if __name__ == "__main__":
    channel = grpc.insecure_channel("localhost:50051")
    stub = service_pb2_grpc.MyServiceStub(channel)
    try:
        response = stub.DoSomething(service_pb2.Request(data="Pichuila"))
        print(response.result)
    except grpc.RpcError as e:
        print(e.details())
        print(e.code())
        print(e.debug_error_string())