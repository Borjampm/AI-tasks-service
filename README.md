# How to generate the protobufs:

```bash
uv run python -m grpc_tools.protoc -I. --python_out=. --pyi_out=. --grpc_python_out=. service.proto
```
where:
- `-I.` is the input directory
- `--python_out=.` is the output directory for message classes
- `--pyi_out=.` is the output directory for type stubs
- `--grpc_python_out=.` is the output directory for grpc service classes
- `service.proto` is the input file

It generates the following files:
- `service_pb2.py` - message classes
- `service_pb2_grpc.py` - grpc service classes
- `service_pb2.pyi` - type stubs
