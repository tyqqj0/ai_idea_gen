from fastapi import APIRouter


router = APIRouter()


@router.get("/ping", summary="简单连通性测试")
async def ping():
    return {"message": "pong"}



