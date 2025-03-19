
(function () {
    function inithcp() {
        code_blocks = Array.from(document.querySelectorAll("code.sourceCode"));
        console.log("There are " + code_blocks.length + " code blocks");
        code_blocks.forEach((ref, index) => {
            if (index != 4) {
                return;
            }
            // For each line
            for (const line of ref.children) {
                let in_block = false;
                let cur_contents = [];
                let newChildren = []
                for (const child of line.childNodes) {
                    console.log(child)
                    if (child.nodeName == "SPAN" && child.className == "op" && child.textContent == "==") {
                        if (in_block) {
                            let newMark = document.createElement("mark");
                            for (const innerChild of cur_contents) {
                                newMark.appendChild(innerChild)
                            }
                            newChildren.push(newMark)
                            in_block = false;
                        } else {
                            cur_contents = []
                            in_block = true;
                        }
                    } else if (in_block) {
                        cur_contents.push(child)
                    } else {
                        newChildren.push(child)
                    }
                }
                line.replaceChildren(...newChildren)
            }
        })
    }
    // Run on DOMContentLoaded.
    document.addEventListener("DOMContentLoaded", inithcp);
})();
