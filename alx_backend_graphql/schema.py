import graphene
from crm.schema import Query as CRMQuery, Mutation as CRMMutation
from graphene_django import DjangoObjectType
from .models import Customer, Product, Order
from django.db import transaction
from django.core.exceptions import ValidationError
import re
from decimal import Decimal
from datetime import datetime

class Query(CRMQuery, graphene.ObjectType):
    hello = graphene.String(default_value="Hello, GraphQL!")

schema = graphene.Schema(query=Query)

class Mutation(CRMMutation, graphene.ObjectType):
    pass

schema = graphene.Schema(query=Query, mutation=Mutation)
# --------------------
# Object Types
# --------------------
class CustomerType(DjangoObjectType):
    class Meta:
        model = Customer

class ProductType(DjangoObjectType):
    class Meta:
        model = Product

class OrderType(DjangoObjectType):
    class Meta:
        model = Order

# --------------------
# Mutations
# --------------------

class CreateCustomer(graphene.Mutation):
    customer = graphene.Field(CustomerType)
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)

    class Arguments:
        name = graphene.String(required=True)
        email = graphene.String(required=True)
        phone = graphene.String()

    def mutate(self, info, name, email, phone=None):
        errors = []

        # Validate email uniqueness
        if Customer.objects.filter(email=email).exists():
            errors.append("Email already exists.")

        # Validate phone format
        if phone:
            pattern = re.compile(r'^(\+\d{10,15}|\d{3}-\d{3}-\d{4})$')
            if not pattern.match(phone):
                errors.append("Phone must be +1234567890 or 123-456-7890.")

        if errors:
            return CreateCustomer(success=False, errors=errors, customer=None)

        customer = Customer(name=name, email=email, phone=phone)
        customer.save()
        return CreateCustomer(customer=customer, success=True, errors=[])

# --------------------
class BulkCreateCustomers(graphene.Mutation):
    customers = graphene.List(CustomerType)
    errors = graphene.List(graphene.String)

    class Arguments:
        customer_list = graphene.List(
            graphene.InputObjectType(
                "CustomerInput",
                name=graphene.String(required=True),
                email=graphene.String(required=True),
                phone=graphene.String()
            )
        )

    def mutate(self, info, customer_list):
        created_customers = []
        errors = []

        with transaction.atomic():
            for idx, cust_data in enumerate(customer_list):
                name = cust_data.get("name")
                email = cust_data.get("email")
                phone = cust_data.get("phone", None)

                if Customer.objects.filter(email=email).exists():
                    errors.append(f"{email} already exists")
                    continue

                if phone:
                    pattern = re.compile(r'^(\+\d{10,15}|\d{3}-\d{3}-\d{4})$')
                    if not pattern.match(phone):
                        errors.append(f"{email}: Invalid phone format")
                        continue

                customer = Customer(name=name, email=email, phone=phone)
                customer.save()
                created_customers.append(customer)

        return BulkCreateCustomers(customers=created_customers, errors=errors)

# --------------------
class CreateProduct(graphene.Mutation):
    product = graphene.Field(ProductType)
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)

    class Arguments:
        name = graphene.String(required=True)
        price = graphene.Float(required=True)
        stock = graphene.Int()

    def mutate(self, info, name, price, stock=0):
        errors = []
        if price <= 0:
            errors.append("Price must be positive.")
        if stock < 0:
            errors.append("Stock cannot be negative.")
        if errors:
            return CreateProduct(success=False, errors=errors, product=None)
        product = Product(name=name, price=Decimal(price), stock=stock)
        product.save()
        return CreateProduct(product=product, success=True, errors=[])

# --------------------
class CreateOrder(graphene.Mutation):
    order = graphene.Field(OrderType)
    success = graphene.Boolean()
    errors = graphene.List(graphene.String)

    class Arguments:
        customer_id = graphene.ID(required=True)
        product_ids = graphene.List(graphene.ID, required=True)
        order_date = graphene.DateTime()

    def mutate(self, info, customer_id, product_ids, order_date=None):
        errors = []

        # Validate customer
        try:
            customer = Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            errors.append("Invalid customer ID.")
            return CreateOrder(success=False, errors=errors, order=None)

        # Validate products
        products = []
        for pid in product_ids:
            try:
                product = Product.objects.get(pk=pid)
                products.append(product)
            except Product.DoesNotExist:
                errors.append(f"Invalid product ID: {pid}")

        if not products:
            errors.append("At least one valid product must be selected.")
            return CreateOrder(success=False, errors=errors, order=None)

        # Default order_date
        if order_date is None:
            order_date = datetime.now()

        order = Order(customer=customer, order_date=order_date)
        order.save()
        order.products.set(products)
        total_amount = sum([p.price for p in products])
        order.total_amount = total_amount
        order.save()

        return CreateOrder(order=order, success=True, errors=[])

# --------------------
# Mutation Class
# --------------------
class Mutation(graphene.ObjectType):
    create_customer = CreateCustomer.Field()
    bulk_create_customers = BulkCreateCustomers.Field()
    create_product = CreateProduct.Field()
    create_order = CreateOrder.Field()