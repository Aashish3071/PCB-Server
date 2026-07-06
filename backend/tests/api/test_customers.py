import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_customer_success(client: AsyncClient):
    payload = {
        "company_name": "Test Company Corp",
        "contact_person": "Jane Doe",
        "contact_email": "jane@example.com"
    }
    response = await client.post("/api/v1/customers", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["company_name"] == "Test Company Corp"
    assert "id" in data
    assert data["contact_person"] == "Jane Doe"

@pytest.mark.asyncio
async def test_create_customer_validation_error(client: AsyncClient):
    # Missing required field company_name
    payload = {
        "contact_person": "Jane Doe"
    }
    response = await client.post("/api/v1/customers", json=payload)
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_get_customer_success(client: AsyncClient):
    # Create first
    create_resp = await client.post("/api/v1/customers", json={"company_name": "Fetch Me"})
    customer_id = create_resp.json()["id"]

    # Fetch
    response = await client.get(f"/api/v1/customers/{customer_id}")
    assert response.status_code == 200
    assert response.json()["company_name"] == "Fetch Me"

@pytest.mark.asyncio
async def test_get_customer_not_found(client: AsyncClient):
    response = await client.get("/api/v1/customers/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_search_customers(client: AsyncClient):
    await client.post("/api/v1/customers", json={"company_name": "Alpha Ltd"})
    await client.post("/api/v1/customers", json={"company_name": "Beta Corp"})

    # Search
    response = await client.get("/api/v1/customers?q=Alpha")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["company_name"] == "Alpha Ltd"

@pytest.mark.asyncio
async def test_invalid_pagination(client: AsyncClient):
    # page=0 is invalid (ge=1)
    response = await client.get("/api/v1/customers?page=0")
    assert response.status_code == 422
    
@pytest.mark.asyncio
async def test_update_customer(client: AsyncClient):
    create_resp = await client.post("/api/v1/customers", json={"company_name": "To Update"})
    customer_id = create_resp.json()["id"]

    update_resp = await client.put(f"/api/v1/customers/{customer_id}", json={"company_name": "Updated Name"})
    assert update_resp.status_code == 200
    assert update_resp.json()["company_name"] == "Updated Name"

@pytest.mark.asyncio
async def test_delete_customer_success(client: AsyncClient):
    create_resp = await client.post("/api/v1/customers", json={"company_name": "To Delete"})
    customer_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/api/v1/customers/{customer_id}")
    assert delete_resp.status_code == 204

    # Verify deleted
    get_resp = await client.get(f"/api/v1/customers/{customer_id}")
    assert get_resp.status_code == 404
