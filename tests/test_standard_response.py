from fastapi_api.core.standard_response import StandardResponse

def test_ok_response():
    response = StandardResponse.ok(data={"name": "Paulines"})

    assert response.success
    assert response.message == "Success"
    assert response.data == {"name": "Paulines"}

def test_error_response():
    response = StandardResponse.error(message="Something went wrong")

    assert response.success == False
    assert response.message == "Something went wrong"
    assert response.data == None