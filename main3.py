from langchain_community.document_loaders import PyPDFLoader
loader = PyPDFLoader("document_loader/GRU.pdf")
docs = loader.load()
print("Pages loaded:", len(docs))
print(docs[0].page_content)
