import Foundation
import PDFKit
let path = CommandLine.arguments[1]
guard let doc = PDFDocument(url: URL(fileURLWithPath: path)) else { print("FAILED to open"); exit(1) }
print("pages: \(doc.pageCount)")
if let t = doc.documentAttributes?[PDFDocumentAttribute.titleAttribute] {
    print("METADATA Title: \(t)")
}
for i in 0..<doc.pageCount {
    if let p = doc.page(at: i), let s = p.string {
        print("---- page \(i+1) text ----")
        print(s)
    }
}
