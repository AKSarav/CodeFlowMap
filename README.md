<p align="center">
  <img src="images/Logo.png" width="300" />
</p>

CodeFlowMap is an Agentic Codebase walk through Agent - Parse through the large codebase and create C4 Architecture diagrams based on the Source grounded information - though backed by AI.  The system is designed with Treesitter and powerful parsing mechanisms and guardrails to keep the outcomes legit and truthful.

We have two modes of implementation right now.

### VS Code Custom Agent

A VS Code Custom Agent that integrates directly into your editor. Point it at your workspace and get architecture diagrams without leaving the IDE.

→ [Read the VS Code README](./vscode/README.md)


### DeepAgent CLI Tool

A CLI deep-agent that runs an autonomous multi-step analysis loop using [LangChain DeepAgents](https://docs.langchain.com/oss/python/deepagents/). Point it at any local repo, approve the plan, and receive a fully generated `codeflowmap.md` file.

→ [Read the DeepAgent README](./deepagent/README.md)


### Samples


```mermaid
graph TD
  subgraph API Layer
    A[AuthMiddleware]
    B[OrderController]
    C[UserController]
  end
  subgraph Business Logic
    D[OrderService]
    E[PaymentService]
    F[UserService]
  end
  subgraph Data Layer
    G[OrderRepository]
    H[UserRepository]
  end
  subgraph External Systems
    I[(PostgreSQL)]
    J[Stripe API]
    K[JWT Provider]
  end

  B -->|"validates token"| A
  A -->|"authenticates via"| K
  B -->|"delegates to"| D
  D -->|"charges via"| E
  D -->|"persists via"| G
  E -->|"HTTP REST"| J
  G -->|"SQL"| I
  H -->|"SQL"| I
```


```mermaid
classDiagram
  class OrderService {
    <<Service>>
    -orderRepo: OrderRepository
    -paymentService: IPaymentService
    +createOrder(userId: string, items: Item[]) Order
    +cancelOrder(orderId: string) void
  }
  class IPaymentService {
    <<Interface>>
    +charge(amount: number, token: string) PaymentResult
    +refund(transactionId: string) void
  }
  class StripePaymentService {
    -client: StripeClient
    +charge(amount: number, token: string) PaymentResult
    +refund(transactionId: string) void
  }
  class Order {
    +id: string
    +userId: string
    +status: OrderStatus
    +totalAmount: number
  }

  OrderService --> IPaymentService : depends on
  IPaymentService <|.. StripePaymentService : implements
  OrderService *-- Order : creates
```

