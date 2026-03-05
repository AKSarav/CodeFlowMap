<p align="center">
  <img src="images/Logo.png" width="300" />
</p>

A VS Code Custom Agent that reads your codebase like a Senior Staff Engineer and maps it into detailed C4-style Mermaid diagrams — at both component and class level.

Here are some samples created by this agent

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

## What is CodeFlowMap?

CodeFlowMap is a **VS Code Custom Agent** powered by GitHub Copilot that analyzes any codebase and automatically generates two levels of architectural diagrams in [Mermaid](https://mermaid.js.org/) syntax:

- **Component Diagram** — C4 Level 3: how your system's runtime components connect and communicate
- **Class Diagram** — C4 Level 4: how your classes, interfaces, and types relate to each other

No manual diagramming. No outdated architecture docs. Just point CodeFlowMap at your codebase and get a clear, navigable map — instantly.


## Why CodeFlowMap?

Every team has that moment:
- A new engineer joins and spends days just figuring out the structure
- A tech lead tries to explain the architecture on a whiteboard from memory
- A PR review stalls because no one is sure how two modules are connected

CodeFlowMap solves this by treating your code as the single source of truth and producing diagrams that actually reflect what's in the repo — not what someone *thought* was there six months ago.


## Features

- **Entry-point aware** — starts from `main()`, server bootstraps, CLI handlers, or exported API surfaces and traces outward
- **Layer detection** — identifies controllers, services, repositories, adapters, domain models, and infrastructure automatically
- **C4-aligned output** — component and class diagrams follow the [C4 model](https://c4model.com/) convention for clarity and consistency
- **Full relationship mapping** — inheritance, composition, aggregation, dependency injection, and interface realization
- **External system awareness** — surfaces databases, third-party APIs, message queues, and caches as first-class diagram nodes
- **Design pattern recognition** — annotates Repository, Factory, Singleton, Strategy, and other patterns with `<<stereotypes>>`
- **Architectural notes** — includes a Staff Engineer-level observations section after every diagram generation
- **Language agnostic** — works with any language or framework supported by VS Code's workspace indexing


## Installation

### Prerequisites

- [Visual Studio Code](https://code.visualstudio.com/) v1.100 or later
- [GitHub Copilot](https://github.com/features/copilot) subscription (Free, Pro, or Team)
- GitHub Copilot extension installed in VS Code

### Setup

1. **Clone or download** this repository

   ```bash
   git clone https://github.com/AKSarav/CodeFlowMap.git
   ```

2. **Copy the agent file** into your project or VS Code user profile:

   **Project-level** (available only in this workspace):
   ```
   your-project/
   └── .github/
       └── agents/
           └── codeflowmap.agent.md   ← paste agent file here
   ```

   **User-level** (available across all workspaces):
   Use the Command Palette:
   ```
   Cmd/Ctrl + Shift + P → Chat: New Custom Agent → User profile
   ```
   Paste the contents of `codeflowmap.agent.md` into the editor that opens.

3. **Reload VS Code** (or run `Developer: Reload Window` from the Command Palette)


## Usage

1. Open the **Chat view** in VS Code (`Ctrl+Alt+I` / `Cmd+Ctrl+I`)
2. Select **CodeFlowMap** from the agents dropdown at the top of the Chat panel
3. Type a prompt:

   ```
   Generate diagrams for this codebase
   ```

   Or scope it to a specific module:

   ```
   Generate diagrams for the /src/auth module
   ```

   Or ask for a specific focus:

   ```
   Map the component diagram for the payment flow only
   ```

4. CodeFlowMap will analyze the workspace, trace the architecture, and output:
   - A codebase summary
   - A Mermaid component diagram
   - A Mermaid class diagram
   - A set of architectural observations

5. **Render the diagrams** by copying the Mermaid code into:
   - [Mermaid Live Editor](https://mermaid.live)
   - A `.mmd` file with the [Mermaid VS Code extension](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid)
   - Any Markdown file with Mermaid rendering (GitHub, Notion, Confluence, etc.)

### Codebase Summary

> A Node.js REST API using a layered architecture (Controller → Service → Repository). Built with Express and TypeScript, backed by PostgreSQL via TypeORM. Payment processing delegated to Stripe. Authentication handled via JWT middleware.

### Component Diagram




## Example Prompts

| What you want | Prompt |
|---|---|
| Full codebase map | `Generate component and class diagrams for this codebase` |
| Single module | `Map the /src/payments module only` |
| Focus on domain layer | `Generate a class diagram for the domain layer only` |
| Specific flow | `Trace the component flow for a user login request` |
| Expand a diagram | `Add the event flow for order processing to the component diagram` |
| Large monorepo | `Generate diagrams for the auth-service package only` |


## How It Works

CodeFlowMap follows a 4-step analysis protocol internally:

1. **Discover Entry Points** — finds `main()` functions, server bootstraps, route registrations, CLI entrypoints, and exported API surfaces
2. **Map Modules & Boundaries** — traverses the directory structure to identify layers, packages, and external dependencies
3. **Trace Class & Interface Structures** — enumerates classes, interfaces, types, and their relationships (inheritance, composition, injection)
4. **Follow Data & Control Flow** — traces how a request or event travels through the system end-to-end

It then produces both diagrams in a single pass with a structured output that's immediately pasteable into any Mermaid renderer.


## Tested and Works Best With

- Node.js / TypeScript projects
- Java / Spring Boot
- Python (FastAPI, Django, Flask)
- Go microservices
- .NET / C# applications
- Any well-structured project with clear module boundaries


> We recommend using a high reasoning LLMs for better results like Claude Haiku, Claude Sonnet, Gemini2.5, Claude Opus are my choices.


## Contributing

Pull requests are welcome. If you find a codebase pattern that CodeFlowMap doesn't handle well, open an issue with a minimal reproduction case and the expected diagram output.

## Samples generated by CodeFlowMap

These samples were created in a single session by CodeFlowMap Agent

### Codebase: 
https://github.com/AKSarav/pdfstract
### LLM model Used
Claude Haiku
### Prompt used ( with little context)


### System Context Components

```mermaid
%% PDFStract System Context & Components Architecture
%% Shows users, entry points (CLI, Web, API), core service factories,
%% 25+ implementations across converters/chunkers/embeddings, and external systems

graph TD
    subgraph "Users & Entry Points"
        U1["👤 CLI User"]
        U2["👤 Web UI User"]
        U3["👤 Python Developer"]
        
        CLI["CLI Entry Point<br/>click CLI<br/>Commands: convert, chunk, embed"]
        WEB["Web API Entry Point<br/>FastAPI<br/>Endpoints: /convert, /embed"]
        LIB["Library API Entry Point<br/>PDFStract class<br/>Methods: convert(), chunk(), embed()"]
    end

    subgraph "Request Router"
        ROUTER["Request Dispatcher<br/>Validate & Route<br/>to appropriate factory"]
    end

    subgraph "Core Factories"
        CONVFAC["Converter Factory<br/>get_converter(name)<br/>Lazy-loads & caches<br/>9 implementations"]
        
        CHUNKFAC["Chunker Factory<br/>get_chunker(name)<br/>Lazy-loads & caches<br/>10 implementations"]
        
        EMBEDFAC["Embeddings Factory<br/>get_wrapper(provider)<br/>Lazy-loads & caches<br/>6 providers"]
    end

    subgraph "PDF Converters"
        C1["PyMuPDF4LLM<br/>Fast text extraction<br/>No ML models"]
        C2["Marker<br/>Best quality<br/>Based on layout"]
        C3["Docling<br/>ML-powered<br/>Structure-aware"]
        C4["PaddleOCR<br/>OCR-based<br/>Handles scans"]
        C5["DeepSeekOCR<br/>Advanced OCR<br/>Multi-language"]
        C6["Pytesseract<br/>Simple OCR<br/>Google Tesseract"]
        C7["Unstructured<br/>Flexible extraction<br/>Multiple formats"]
        C8["MarkItDown<br/>Fast extraction<br/>Via local binary"]
        C9["MinerU<br/>CLI-based<br/>Offline capable"]
    end

    subgraph "Text Chunkers"
        Ch1["TokenChunker<br/>Fixed token size"]
        Ch2["SentenceChunker<br/>Respects boundaries"]
        Ch3["RecursiveChunker<br/>Hierarchical"]
        Ch4["SemanticChunker<br/>Embedding-based similarity"]
        Ch5["CodeChunker<br/>AST-aware for code"]
        Ch6["TableChunker<br/>Markdown tables"]
        Ch7["LateChunker<br/>ColBERT retrieval"]
        Ch8["NeuralChunker<br/>Boundary detection"]
        Ch9["FastChunker<br/>Regex-based"]
        Ch10["SlumberChunker<br/>LLM-powered"]
    end

    subgraph "Embedding Providers"
        E1["OpenAI<br/>text-embedding-3"]
        E2["Azure OpenAI<br/>Enterprise"]
        E3["Google Generative<br/>Gemini"]
        E4["Ollama<br/>Local models"]
        E5["Sentence-Transformers<br/>Lightweight local"]
        E6["Model2Vec<br/>Gensim-based"]
    end

    subgraph "Support Services"
        DB["Database Service<br/>SQLite metadata<br/>Store results"]
        QM["Queue Manager<br/>Parallel processing<br/>Worker threads"]
        RM["Results Manager<br/>File storage<br/>~/.pdfstract/results"]
        LOG["Logger<br/>Loguru<br/>~/.pdfstract/logs"]
    end

    subgraph "External Systems"
        PDFFILE["PDF Files<br/>.pdf, .pptx, .docx<br/>et al"]
        EXTAPI["External LLM APIs<br/>OpenAI, Azure,<br/>Google, Ollama"]
        OCRENG["OCR Engines<br/>PaddleOCR, DeepSeek<br/>Tesseract, Unstructured"]
        CACHE["Model Cache<br/>HF transformers<br/>~/,cache/huggingface"]
    end

    %% User flows
    U1 -->|"invokes"| CLI
    U2 -->|"accesses"| WEB
    U3 -->|"imports"| LIB

    CLI -->|"sends request"| ROUTER
    WEB -->|"sends request"| ROUTER
    LIB -->|"sends request"| ROUTER

    %% Router distributes
    ROUTER -->|"orchestrates"| CONVFAC
    ROUTER -->|"orchestrates"| CHUNKFAC
    ROUTER -->|"orchestrates"| EMBEDFAC
    ROUTER -->|"uses"| QM
    ROUTER -->|"uses"| LOG

    %% Factory implementations
    CONVFAC -->|"manages"| C1
    CONVFAC -->|"manages"| C2
    CONVFAC -->|"manages"| C3
    CONVFAC -->|"manages"| C4
    CONVFAC -->|"manages"| C5
    CONVFAC -->|"manages"| C6
    CONVFAC -->|"manages"| C7
    CONVFAC -->|"manages"| C8
    CONVFAC -->|"manages"| C9

    CHUNKFAC -->|"manages"| Ch1
    CHUNKFAC -->|"manages"| Ch2
    CHUNKFAC -->|"manages"| Ch3
    CHUNKFAC -->|"manages"| Ch4
    CHUNKFAC -->|"manages"| Ch5
    CHUNKFAC -->|"manages"| Ch6
    CHUNKFAC -->|"manages"| Ch7
    CHUNKFAC -->|"manages"| Ch8
    CHUNKFAC -->|"manages"| Ch9
    CHUNKFAC -->|"manages"| Ch10

    EMBEDFAC -->|"manages"| E1
    EMBEDFAC -->|"manages"| E2
    EMBEDFAC -->|"manages"| E3
    EMBEDFAC -->|"manages"| E4
    EMBEDFAC -->|"manages"| E5
    EMBEDFAC -->|"manages"| E6

    %% Converters access externals
    C1 -->|"reads"| PDFFILE
    C2 -->|"reads"| PDFFILE
    C3 -->|"reads"| PDFFILE
    C4 -->|"uses"| OCRENG
    C5 -->|"uses"| OCRENG
    C6 -->|"uses"| OCRENG
    C7 -->|"reads"| PDFFILE
    C8 -->|"reads"| PDFFILE
    C9 -->|"uses"| OCRENG

    %% Chunkers may use embeddings
    Ch4 -->|"requires"| EMBEDFAC
    Ch7 -->|"requires"| EMBEDFAC
    Ch8 -->|"may use"| EMBEDFAC

    %% Embeddings call external APIs
    E1 -->|"calls"| EXTAPI
    E2 -->|"calls"| EXTAPI
    E3 -->|"calls"| EXTAPI
    E4 -->|"calls"| EXTAPI
    E5 -->|"downloads models"| CACHE
    E6 -->|"downloads models"| CACHE

    %% All write to DB
    CONVFAC -->|"stores metadata"| DB
    CHUNKFAC -->|"stores chunks"| DB
    EMBEDFAC -->|"stores embeddings"| DB

    %% Support services
    CONVFAC -->|"logs"| LOG
    CHUNKFAC -->|"logs"| LOG
    EMBEDFAC -->|"logs"| LOG
    DB -->|"logs"| LOG

    CONVFAC -->|"distributes"| QM
    CHUNKFAC -->|"distributes"| QM
    EMBEDFAC -->|"distributes"| QM

    CONVFAC -->|"saves results"| RM
    CHUNKFAC -->|"saves results"| RM
    EMBEDFAC -->|"saves results"| RM

    %% Styling
    style U1 fill:#e3f2fd
    style U2 fill:#e3f2fd
    style U3 fill:#e3f2fd
    style CLI fill:#bbdefb
    style WEB fill:#bbdefb
    style LIB fill:#bbdefb
    style ROUTER fill:#fff9c4
    
    style CONVFAC fill:#fff3e0
    style C1 fill:#fff3e0
    style C2 fill:#fff3e0
    style C3 fill:#fff3e0
    style C4 fill:#fff3e0
    style C5 fill:#fff3e0
    style C6 fill:#fff3e0
    style C7 fill:#fff3e0
    style C8 fill:#fff3e0
    style C9 fill:#fff3e0
    
    style CHUNKFAC fill:#f3e5f5
    style Ch1 fill:#f3e5f5
    style Ch2 fill:#f3e5f5
    style Ch3 fill:#f3e5f5
    style Ch4 fill:#f3e5f5
    style Ch5 fill:#f3e5f5
    style Ch6 fill:#f3e5f5
    style Ch7 fill:#f3e5f5
    style Ch8 fill:#f3e5f5
    style Ch9 fill:#f3e5f5
    style Ch10 fill:#f3e5f5
    
    style EMBEDFAC fill:#e8f5e9
    style E1 fill:#e8f5e9
    style E2 fill:#e8f5e9
    style E3 fill:#e8f5e9
    style E4 fill:#e8f5e9
    style E5 fill:#e8f5e9
    style E6 fill:#e8f5e9
    
    style DB fill:#ffccbc
    style QM fill:#ffe0b2
    style RM fill:#ffe0b2
    style LOG fill:#ffe0b2
    
    style PDFFILE fill:#ffccbc
    style EXTAPI fill:#ffccbc
    style OCRENG fill:#ffccbc
    style CACHE fill:#ffccbc

```

### converter layer
```mermaid
%% PDFStract Converter Layer - Class Diagram (C4 Level 4)
%% Shows PDFConverter abstract base class, concrete implementations,
%% output format/status enums, and factory classes

classDiagram
    class OutputFormat {
        <<Enumeration>>
        MARKDOWN = "markdown"
        JSON = "json"
        PYMUPDF = "pymupdf"
        TEXT = "text"
    }

    class DownloadStatus {
        <<Enumeration>>
        SUCCESS = "success"
        FAILED = "failed"
        PARTIAL = "partial"
    }

    class PDFConverter {
        <<Abstract>>
        #name: str*
        #available: bool*
        #output_formats: List~str~*
        #supports_ocr: bool
        #description: str
        +convert(pdf_path: str, **kwargs)* str
        +download_model(**kwargs)* DownloadStatus
        +validate_installation() bool*
        +get_info() Dict*
    }

    class PyMuPDF4LLMConverter {
        +name: "pymupdf4llm"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: false
        +convert(pdf_path, **kwargs) str
        +download_model() DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class MarkerConverter {
        -_model_cache: Optional
        +name: "marker"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: false
        +convert(pdf_path, device_map, batch_size) str
        +download_model(device_map, batch_size) DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class DoclingConverter {
        -_converter_cache: Optional
        +name: "docling"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: true
        +convert(pdf_path, max_pages) str
        +download_model() DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class PaddleOCRConverter {
        -_ocr_cache: Optional
        +name: "paddleocr"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: true
        +convert(pdf_path, lang, device) str
        +download_model(device, lang) DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class DeepSeekOCRConverter {
        -_model_cache: Optional
        +name: "deepseek"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: true
        +convert(pdf_path, lang, detection_model) str
        +download_model(detection_model) DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class PytesseractConverter {
        +name: "pytesseract"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: true
        +convert(pdf_path, lang) str
        +download_model(lang) DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class UnstructuredConverter {
        +name: "unstructured"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: true
        +convert(pdf_path, strategy) str
        +download_model() DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class MarkItDownConverter {
        +name: "markitdown"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: false
        +convert(pdf_path) str
        +download_model() DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class MinerUConverter {
        -_mineru_path: str
        +name: "mineru"
        +available: bool
        +output_formats: List~str~
        +supports_ocr: true
        +convert(pdf_path, device_id, backend) str
        +download_model(backend) DownloadStatus
        +validate_installation() bool
        +get_info() Dict
    }

    class CLILazyFactory {
        <<Factory>>
        -_converters: Dict~str, PDFConverter~
        +get_converter(name: str) PDFConverter
        +list_converters() List~str~
        +get_default_converter() PDFConverter
    }

    class OCRFactory {
        <<Factory>>
        -_ocr_converters: Dict~str, PDFConverter~
        +get_ocr_converter(name: str) PDFConverter
        +list_ocr_converters() List~str~
        +prepare_ocr_models(converters: List) DownloadStatus
    }

    %% Inheritance
    PDFConverter <|-- PyMuPDF4LLMConverter
    PDFConverter <|-- MarkerConverter
    PDFConverter <|-- DoclingConverter
    PDFConverter <|-- PaddleOCRConverter
    PDFConverter <|-- DeepSeekOCRConverter
    PDFConverter <|-- PytesseractConverter
    PDFConverter <|-- UnstructuredConverter
    PDFConverter <|-- MarkItDownConverter
    PDFConverter <|-- MinerUConverter

    %% Composition / Usage
    PDFConverter --> OutputFormat : "uses"
    PDFConverter --> DownloadStatus : "uses"
    CLILazyFactory --> PyMuPDF4LLMConverter : "manages"
    CLILazyFactory --> MarkerConverter : "manages"
    CLILazyFactory --> DoclingConverter : "manages"
    CLILazyFactory --> PaddleOCRConverter : "manages"
    CLILazyFactory --> DeepSeekOCRConverter : "manages"
    CLILazyFactory --> PytesseractConverter : "manages"
    CLILazyFactory --> UnstructuredConverter : "manages"
    CLILazyFactory --> MarkItDownConverter : "manages"
    CLILazyFactory --> MinerUConverter : "manages"

    OCRFactory --> PaddleOCRConverter : "manages OCR"
    OCRFactory --> DeepSeekOCRConverter : "manages OCR"
    OCRFactory --> PytesseractConverter : "manages OCR"
    OCRFactory --> MinerUConverter : "manages OCR"
    OCRFactory --> DoclingConverter : "manages OCR-capable"
```
### chunker layer  
```mermaid
%% PDFStract Chunker Layer - Class Diagram (C4 Level 4)
%% Shows BaseChunker abstract base, Chunk/ChunkingResult dataclasses,
%% 10 concrete chunker implementations, and ChunkerFactory

classDiagram
    class Chunk {
        +text: str
        +start_index: int
        +end_index: int
        +token_count: int
        +metadata: Dict~str, Any~
        +to_dict() Dict
        +__len__() int
    }

    class ChunkingResult {
        +chunks: List~Chunk~
        +chunker_name: str
        +parameters: Dict~str, Any~
        +total_chunks: int
        +total_tokens: int
        +original_length: int
        +to_dict() Dict
    }

    class ChunkerType {
        <<Enumeration>>
        TOKEN = "token"
        FAST = "fast"
        SENTENCE = "sentence"
        RECURSIVE = "recursive"
        SEMANTIC = "semantic"
        CODE = "code"
        TABLE = "table"
        LATE = "late"
        NEURAL = "neural"
        SLUMBER = "slumber"
    }

    class BaseChunker {
        <<Abstract>>
        #name: str*
        #available: bool*
        #parameters_schema: Dict*
        #error_message: Optional~str~
        #description: str
        +chunk(text, **params)* List~Chunk~
        +chunk_with_result(text, **params) ChunkingResult
        +validate_params(params) Dict
        +get_info() Dict
    }

    class TokenChunkerWrapper {
        -_chunker_cache: Dict
        +name: "token"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, tokenizer, chunk_size, chunk_overlap) List~Chunk~
    }

    class SentenceChunkerWrapper {
        -_chunker_cache: Dict
        +name: "sentence"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, tokenizer, chunk_size, chunk_overlap, min_sentences) List~Chunk~
    }

    class RecursiveChunkerWrapper {
        -_chunker_cache: Dict
        +name: "recursive"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, tokenizer, chunk_size, recipe) List~Chunk~
    }

    class SemanticChunkerWrapper {
        -_chunker_cache: Dict
        +name: "semantic"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, embedding_model, chunk_size, threshold) List~Chunk~
    }

    class CodeChunkerWrapper {
        -_chunker_cache: Dict
        +name: "code"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, language, tokenizer, chunk_size) List~Chunk~
    }

    class TableChunkerWrapper {
        -_chunker_cache: Dict
        +name: "table"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, tokenizer, chunk_size) List~Chunk~
    }

    class LateChunkerWrapper {
        -_chunker_cache: Dict
        +name: "late"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, embedding_model, chunk_size) List~Chunk~
    }

    class NeuralChunkerWrapper {
        -_chunker_cache: Dict
        +name: "neural"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, model, device_map, stride) List~Chunk~
    }

    class FastChunkerWrapper {
        -_chunker_cache: Dict
        +name: "fast"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, chunk_size, delimiters, pattern) List~Chunk~
    }

    class SlumberChunkerWrapper {
        -_chunker_cache: Dict
        +name: "slumber"
        +available: bool
        +parameters_schema: Dict
        +chunk(text, genie_provider, tokenizer, chunk_size) List~Chunk~
    }

    class ChunkerFactory {
        -_chunkers: Dict~str, BaseChunker~
        +get_chunker(name) BaseChunker
        +get_default_chunker() BaseChunker
        +list_available_chunkers() List~str~
        +list_all_chunkers() List~Dict~
        +chunk(chunker_name, text, **params)* List~Chunk~
        +chunk_with_result(chunker_name, text, **params)* ChunkingResult
        +get_chunker_schema(chunker_name) Dict
    }

    %% Module-level function
    class get_chunker_factory {
        <<Function>>
        -_factory: Optional~ChunkerFactory~
        +get_chunker_factory()$ ChunkerFactory
    }

    %% Relationships
    BaseChunker --> Chunk : "produces"
    BaseChunker --> ChunkingResult : "produces"
    BaseChunker --> ChunkerType : "uses"

    BaseChunker <|-- TokenChunkerWrapper
    BaseChunker <|-- SentenceChunkerWrapper
    BaseChunker <|-- RecursiveChunkerWrapper
    BaseChunker <|-- SemanticChunkerWrapper
    BaseChunker <|-- CodeChunkerWrapper
    BaseChunker <|-- TableChunkerWrapper
    BaseChunker <|-- LateChunkerWrapper
    BaseChunker <|-- NeuralChunkerWrapper
    BaseChunker <|-- FastChunkerWrapper
    BaseChunker <|-- SlumberChunkerWrapper

    ChunkerFactory --> BaseChunker : "manages 10 implementations"
    ChunkerFactory --> Chunk : "returns"
    ChunkerFactory --> ChunkingResult : "returns"
    get_chunker_factory --> ChunkerFactory : "returns singleton"
```

### embedding layer
```mermaid
%% PDFStract Embedding Layer - Class Diagram (C4 Level 4)
%% Shows BaseEmbeddingsWrapper abstract base, 6 concrete provider wrappers,
%% EmbeddingResult/EmbeddingsConfig, and EmbeddingsFactory

classDiagram
    class EmbeddingResult {
        +text: str
        +embedding: List~float~
        +model: str
        +dimension: int
        +to_dict() Dict
    }

    class EmbeddingsConfig {
        <<Interface>>
        +provider: str
        +model: str
        +api_key: Optional~str~
        +api_base: Optional~str~
        +api_version: Optional~str~
    }

    class BaseEmbeddingsWrapper {
        <<Abstract>>
        #provider_name: str*
        #available: bool*
        #description: str
        #embedding_dimension: int
        #supported_languages: List~str~*
        +embed(text, **kwargs)* EmbeddingResult
        +embed_batch(texts, **kwargs)* List~EmbeddingResult~
        +validate_credentials() bool*
        +get_model_info() Dict*
    }

    class OpenAIEmbeddingsWrapper {
        -_client: Optional~OpenAI~
        -_async_client: Optional~AsyncOpenAI~
        -_model: str
        -_organization: Optional~str~
        +provider_name: "openai"
        +available: bool
        +embedding_dimension: int
        +embed(text, timeout) EmbeddingResult
        +embed_batch(texts, timeout, show_progress) List~EmbeddingResult~
        +embed_async(text, timeout) EmbeddingResult
        +embed_batch_async(texts, timeout) List~EmbeddingResult~
        +validate_credentials() bool
        +get_model_info() Dict
    }

    class AzureOpenAIEmbeddingsWrapper {
        -_client: Optional~AzureOpenAI~
        -_async_client: Optional~AsyncAzureOpenAI~
        -_model: str
        -_deployment_name: str
        +provider_name: "azure-openai"
        +available: bool
        +embedding_dimension: int
        +embed(text, timeout) EmbeddingResult
        +embed_batch(texts, timeout, show_progress) List~EmbeddingResult~
        +embed_async(text, timeout) EmbeddingResult
        +embed_batch_async(texts, timeout) List~EmbeddingResult~
        +validate_credentials() bool
        +get_model_info() Dict
    }

    class GoogleEmbeddingsWrapper {
        -_client: Optional~genai.Client~
        -_model: str
        +provider_name: "google"
        +available: bool
        +embedding_dimension: int
        +embed(text, timeout) EmbeddingResult
        +embed_batch(texts, timeout, show_progress) List~EmbeddingResult~
        +validate_credentials() bool
        +get_model_info() Dict
    }

    class OllamaEmbeddingsWrapper {
        -_client: Optional~requests.Session~
        -_model: str
        -_base_url: str
        +provider_name: "ollama"
        +available: bool
        +embedding_dimension: int
        +embed(text, timeout) EmbeddingResult
        +embed_batch(texts, timeout, show_progress) List~EmbeddingResult~
        +validate_credentials() bool
        +get_model_info() Dict
    }

    class SentenceTransformersEmbeddingsWrapper {
        -_model: Optional~SentenceTransformer~
        -_model_name: str
        -_device: str
        +provider_name: "sentence-transformers"
        +available: bool
        +embedding_dimension: int
        +embed(text) EmbeddingResult
        +embed_batch(texts, batch_size, show_progress) List~EmbeddingResult~
        +validate_credentials() bool
        +get_model_info() Dict
    }

    class Model2VecEmbeddingsWrapper {
        -_model: Optional~Model2Vec~
        -_model_name: str
        +provider_name: "model2vec"
        +available: bool
        +embedding_dimension: int
        +embed(text) EmbeddingResult
        +embed_batch(texts, show_progress) List~EmbeddingResult~
        +validate_credentials() bool
        +get_model_info() Dict
    }

    class EmbeddingProvider {
        <<Enumeration>>
        OPENAI = "openai"
        AZURE_OPENAI = "azure-openai"
        GOOGLE = "google"
        OLLAMA = "ollama"
        SENTENCE_TRANSFORMERS = "sentence-transformers"
        MODEL2VEC = "model2vec"
    }

    class EmbeddingsFactory {
        -_wrappers: Dict~str, Type~BaseEmbeddingsWrapper~~
        -_instances: Dict~str, BaseEmbeddingsWrapper~
        +get_embeddings_wrapper(provider: str, **kwargs) BaseEmbeddingsWrapper
        +list_available_providers() List~str~
        +list_all_providers() List~Dict~
        +embed(provider, text, **kwargs)* EmbeddingResult
        +embed_batch(provider, texts, **kwargs)* List~EmbeddingResult~
        +validate_provider_config(provider, **kwargs) bool
        +get_provider_info(provider) Dict
        +get_default_provider() str
    }

    class get_embeddings_factory {
        <<Function>>
        -_factory: Optional~EmbeddingsFactory~
        +get_embeddings_factory()$ EmbeddingsFactory
    }

    %% Relationships
    BaseEmbeddingsWrapper --> EmbeddingResult : "produces"
    BaseEmbeddingsWrapper --> EmbeddingProvider : "uses"
    BaseEmbeddingsWrapper --> EmbeddingsConfig : "configures from"

    BaseEmbeddingsWrapper <|-- OpenAIEmbeddingsWrapper
    BaseEmbeddingsWrapper <|-- AzureOpenAIEmbeddingsWrapper
    BaseEmbeddingsWrapper <|-- GoogleEmbeddingsWrapper
    BaseEmbeddingsWrapper <|-- OllamaEmbeddingsWrapper
    BaseEmbeddingsWrapper <|-- SentenceTransformersEmbeddingsWrapper
    BaseEmbeddingsWrapper <|-- Model2VecEmbeddingsWrapper

    EmbeddingsFactory --> BaseEmbeddingsWrapper : "manages 6 providers"
    EmbeddingsFactory --> EmbeddingResult : "returns"
    EmbeddingsFactory --> EmbeddingProvider : "uses"
    get_embeddings_factory --> EmbeddingsFactory : "returns singleton"

```

### sequence
```mermaid
%% PDFStract Interaction Sequence Diagram
%% Shows temporal flow of a typical convert + chunk + embed workflow

sequenceDiagram
    participant User as User/CLI/API
    participant Validator as Request Validator
    participant ConvFac as Converter Factory
    participant Converter as PDF Converter
    participant ChunkFac as Chunker Factory
    participant Chunker as Text Chunker
    participant EmbFac as Embeddings Factory
    participant Embeddings as Embedding Wrapper
    participant ExtAPI as External System

    User->>Validator: convert(pdf, converter, chunker, provider)
    Validator->>Validator: validate input
    
    Validator->>ConvFac: get_converter(name)
    ConvFac->>ConvFac: cache lookup
    ConvFac->>Converter: create instance
    ConvFac-->>Validator: Converter
    
    Validator->>Converter: convert(pdf_path)
    Converter->>ExtAPI: read & extract text
    Converter-->>Validator: text
    
    Validator->>ChunkFac: get_chunker(name)
    ChunkFac->>ChunkFac: cache lookup
    ChunkFac->>Chunker: create instance
    ChunkFac-->>Validator: Chunker
    
    Validator->>Chunker: chunk(text)
    Chunker->>Chunker: split text to chunks
    Chunker-->>Validator: List~Chunk~
    
    Validator->>EmbFac: get_wrapper(provider)
    EmbFac->>EmbFac: cache lookup
    EmbFac->>Embeddings: create instance
    EmbFac-->>Validator: Wrapper
    
    Validator->>Embeddings: embed_batch(chunks)
    Embeddings->>ExtAPI: call LLM/local model
    ExtAPI-->>Embeddings: embeddings
    Embeddings-->>Validator: List~EmbeddingResult~
    
    Validator-->>User: ChunkingResult with embeddings
```
---

## License

MIT © [AKSarav](https://github.com/AKSarav)
