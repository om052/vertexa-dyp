"""Original, version-controlled starter lessons for the four supported languages."""

CURRICULUM = (
    {
        "code": "python",
        "name": "Python",
        "position": 0,
        "description": "A gentle path from your first Python program to functions, "
        "collections, and debugging.",
        "topics": (
            (
                "getting-started",
                "Getting started",
                "What a program is and how to run Python code.",
                "beginner",
                "Meet Python",
                "Learn what an interpreter does and how to run a saved Python file.",
                "A Python interpreter reads and runs your instructions. Save code "
                "in a file ending in `.py`, then run it with `python hello.py`. "
                "Try `python --version` to check that Python is available. Use "
                "Python 3 for new projects.",
                None,
            ),
            (
                "first-output",
                "Output and your first program",
                "Display a message and understand how Python runs statements.",
                "beginner",
                "Print a message",
                "Use `print` to send readable output to the terminal.",
                "The `print` function displays a value. Python runs statements "
                "from top to bottom.\n\n```python\nprint(\"Hello, world!\")\n```",
                ("getting-started", "getting-started"),
            ),
            (
                "variables-and-types",
                "Variables and basic types",
                "Give values names and recognize common built-in types.",
                "beginner",
                "Name and inspect values",
                "Assign values and identify strings, integers, and booleans.",
                "Use `=` to bind a name to a value. Python determines the value's "
                "type at runtime.\n\n```python\nname = \"Ari\"       # str\n"
                "lessons = 3       # int\nready = True      # bool\n"
                "print(type(lessons))\n```",
                ("first-output", "first-output"),
            ),
            (
                "input-and-output",
                "Input and output",
                "Read text from a person and convert it when a number is needed.",
                "beginner",
                "Read a name",
                "Use `input` and understand that it returns text.",
                "`input` pauses for text and always returns a string. Convert "
                "numeric text explicitly before arithmetic.\n\n```python\n"
                "name = input(\"Your name: \")\nprint(\"Hello,\", name)\n```",
                ("variables-and-types", "variables-and-types"),
            ),
            (
                "operators",
                "Operators and expressions",
                "Calculate with arithmetic and compare values.",
                "beginner",
                "Calculate and compare",
                "Use arithmetic operators and comparisons to produce values.",
                "Python uses `+`, `-`, `*`, `/`, and `//` for common arithmetic. "
                "Comparisons such as `>=` produce a boolean.\n\n```python\n"
                "price = 4 * 3\nprint(price >= 10)  # True\n```",
                ("input-and-output", "input-and-output"),
            ),
            (
                "conditionals",
                "Conditional statements",
                "Choose which statements run with `if`, `elif`, and `else`.",
                "beginner",
                "Make a decision",
                "Branch on a condition and keep Python's indentation consistent.",
                "An `if` statement runs its indented block when its condition is "
                "true. `elif` checks another condition and `else` handles the "
                "remaining case.\n\n```python\nscore = 7\nif score >= 10:\n"
                "    print(\"Ready\")\nelse:\n    print(\"Keep practicing\")\n```",
                ("operators", "operators"),
            ),
            (
                "loops",
                "Loops",
                "Repeat work with `for` and `while` loops.",
                "beginner",
                "Repeat a task",
                "Use `for` to visit a sequence and `while` for a condition-controlled loop.",
                "A `for` loop visits each item in an iterable. `range(3)` produces "
                "0, 1, and 2. A `while` loop repeats while its condition stays "
                "true, so update state to avoid an endless loop.\n\n```python\n"
                "for number in range(3):\n    print(number)\n```",
                ("conditionals", "conditionals"),
            ),
            (
                "functions",
                "Functions",
                "Group reusable instructions and return a result.",
                "beginner",
                "Define a function",
                "Create a function with a parameter and an explicit return value.",
                "Define a function with `def`. Parameters receive inputs and "
                "`return` sends a result back to the caller.\n\n```python\n"
                "def double(number):\n    return number * 2\n\n"
                "print(double(4))\n```",
                ("loops", "loops"),
            ),
            (
                "lists-and-strings",
                "Lists and strings",
                "Work with Python lists and inspect individual characters in strings.",
                "beginner",
                "Use a list and a string",
                "Create a list, access an item by index, and inspect a string.",
                "A Python list is an ordered, mutable collection. Indexes start "
                "at zero. Strings are immutable sequences of characters.\n\n"
                "```python\ncolors = [\"blue\", \"gold\"]\n"
                "print(colors[0])\nprint(\"hello\"[1])  # e\n```",
                ("functions", "functions"),
            ),
            (
                "problem-solving",
                "Problem-solving and debugging",
                "Break a small task into steps and use tracebacks to find errors.",
                "beginner",
                "Trace a small program",
                "Reproduce a problem, inspect the traceback, and test a small fix.",
                "When code fails, read the last line of the traceback for the "
                "error type and message, then inspect the referenced line. Change "
                "one thing at a time and rerun a small example. A `SyntaxError` "
                "means Python could not parse the code; a `NameError` often means "
                "a name is misspelled or not defined.",
                ("lists-and-strings", "lists-and-strings"),
            ),
        ),
    },
    {
        "code": "javascript",
        "name": "JavaScript",
        "position": 1,
        "description": "A beginner path through JavaScript values, browser output, "
        "control flow, functions, arrays, and debugging.",
        "topics": (
            (
                "getting-started",
                "Getting started",
                "Where JavaScript runs and how to try a small script.",
                "beginner",
                "Meet JavaScript",
                "Recognize JavaScript's runtimes and run a small script.",
                "JavaScript runs in browsers and other runtimes such as Node.js. "
                "In a browser, open developer tools and use the Console. With "
                "Node.js, save a file as `hello.js` and run `node hello.js`. "
                "The same language can be hosted in different environments.",
                None,
            ),
            (
                "first-output",
                "Output and your first program",
                "Write a statement and display text in a developer console.",
                "beginner",
                "Log a message",
                "Use `console.log` and notice the statement terminator.",
                "`console.log` writes a value to the developer console. Semicolons "
                "are commonly used to end statements.\n\n```javascript\n"
                "console.log(\"Hello, world!\");\n```",
                ("getting-started", "getting-started"),
            ),
            (
                "variables-and-types",
                "Variables and basic types",
                "Declare bindings and recognize JavaScript's primitive values.",
                "beginner",
                "Declare values",
                "Use `const` for a binding you will not reassign and `let` when it changes.",
                "Use `const` when a binding will not be reassigned and `let` when "
                "it will. JavaScript values have types such as string, number, "
                "boolean, and `undefined`.\n\n```javascript\nconst name = \"Ari\";\n"
                "let lessons = 3;\nlessons += 1;\nconsole.log(typeof name);\n```",
                ("first-output", "first-output"),
            ),
            (
                "input-and-output",
                "Input and output",
                "Read browser input and write a response without assuming Node has a prompt.",
                "beginner",
                "Read a browser prompt",
                "Use `prompt` in a browser and handle the possibility of cancellation.",
                "In a browser, `prompt` asks for text and returns either a string or "
                "`null` if canceled. It is a browser API, not a built-in Node.js "
                "prompt.\n\n```javascript\nconst name = prompt(\"Your name?\");\n"
                "if (name !== null) console.log(`Hello, ${name}`);\n```",
                ("variables-and-types", "variables-and-types"),
            ),
            (
                "operators",
                "Operators and expressions",
                "Use arithmetic, comparisons, and strict equality.",
                "beginner",
                "Calculate and compare",
                "Combine arithmetic with comparisons and distinguish strict equality.",
                "JavaScript supports arithmetic such as `+` and `*`. Prefer `===` "
                "for equality checks because it does not coerce unlike types.\n\n"
                "```javascript\nconst total = 4 * 3;\nconsole.log(total === 12);\n```",
                ("input-and-output", "input-and-output"),
            ),
            (
                "conditionals",
                "Conditional statements",
                "Choose a branch using `if`, `else if`, and `else`.",
                "beginner",
                "Make a decision",
                "Write a conditional and compare values explicitly.",
                "An `if` statement runs a block when its condition is truthy. "
                "`else if` checks another condition; `else` covers the remaining "
                "case.\n\n```javascript\nconst score = 7;\nif (score >= 10) {\n"
                "  console.log(\"Ready\");\n} else {\n  console.log(\"Practice\");\n}\n```",
                ("operators", "operators"),
            ),
            (
                "loops",
                "Loops",
                "Repeat instructions using `for` and `while`.",
                "beginner",
                "Count with a loop",
                "Use a counted loop and understand its start, condition, and update.",
                "A `for` loop has an initializer, a condition, and an update. The "
                "condition is checked before each iteration. A `while` loop is "
                "useful when repetition depends on a condition.\n\n```javascript\n"
                "for (let count = 0; count < 3; count += 1) {\n"
                "  console.log(count);\n}\n```",
                ("conditionals", "conditionals"),
            ),
            (
                "functions",
                "Functions",
                "Define reusable functions with parameters and return values.",
                "beginner",
                "Return a result",
                "Define a function declaration and call it with an argument.",
                "A function declaration names reusable instructions. Parameters "
                "receive arguments, and `return` gives a result to the caller.\n\n"
                "```javascript\nfunction double(number) {\n  return number * 2;\n"
                "}\nconsole.log(double(4));\n```",
                ("loops", "loops"),
            ),
            (
                "arrays-and-strings",
                "Arrays and strings",
                "Access JavaScript array items and string characters by index.",
                "beginner",
                "Use an array and a string",
                "Create an array and read zero-based indexed values.",
                "JavaScript arrays are ordered objects that can grow or shrink. "
                "Indexes start at zero. Strings are immutable sequences of "
                "UTF-16 code units, so advanced text processing needs care.\n\n"
                "```javascript\nconst colors = [\"blue\", \"gold\"];\n"
                "console.log(colors[0]);\nconsole.log(\"hello\"[1]); // e\n```",
                ("functions", "functions"),
            ),
            (
                "problem-solving",
                "Problem-solving and debugging",
                "Use browser or Node developer tools to inspect and reproduce errors.",
                "beginner",
                "Inspect an error",
                "Read an error message and use a debugger or a small console check.",
                "Reproduce an error with the smallest input you can. Read the "
                "message and stack trace, check the indicated file and line, and "
                "inspect values with `console.log` or a debugger. Fix one cause "
                "at a time and rerun the example.",
                ("arrays-and-strings", "arrays-and-strings"),
            ),
        ),
    },
    {
        "code": "c",
        "name": "C",
        "position": 2,
        "description": "A beginner path through compiling C programs, typed values, "
        "input, control flow, functions, arrays, and debugging.",
        "topics": (
            (
                "getting-started",
                "Getting started",
                "Understand source files, a compiler, and a basic build/run cycle.",
                "beginner",
                "Meet C and the compiler",
                "Learn that C source is compiled before the resulting program runs.",
                "C source is commonly saved in a `.c` file. A compiler translates "
                "it into an executable; for example, `cc hello.c -o hello`, then "
                "run the executable. The exact command depends on your operating "
                "system and installed compiler.",
                None,
            ),
            (
                "first-output",
                "Output and your first program",
                "Understand `main`, a header, formatted output, and the return value.",
                "beginner",
                "Print from `main`",
                "Identify a C program's entry point and a formatted output call.",
                "A hosted C program starts at `main`. Include `<stdio.h>` to "
                "declare `printf`. The `\\n` starts a new line and `return 0` "
                "reports successful completion.\n\n```c\n#include <stdio.h>\n"
                "int main(void) {\n    printf(\"Hello, world!\\n\");\n"
                "    return 0;\n}\n```",
                ("getting-started", "getting-started"),
            ),
            (
                "variables-and-types",
                "Variables and basic types",
                "Declare typed variables and use format specifiers carefully.",
                "beginner",
                "Declare typed values",
                "Recognize `int`, `double`, and character arrays used for text.",
                "C variables have declared types. An `int` stores an integer and "
                "a `double` stores a floating-point value. A C string is usually "
                "a null-terminated character array, not a separate built-in "
                "string type.\n\n```c\nint lessons = 3;\ndouble ratio = 0.5;\n"
                "printf(\"%d %.1f\\n\", lessons, ratio);\n```",
                ("first-output", "first-output"),
            ),
            (
                "input-and-output",
                "Input and output",
                "Read formatted input and check whether conversion succeeded.",
                "beginner",
                "Read an integer safely",
                "Use `scanf`'s return value to detect a successful conversion.",
                "`scanf` stores input through a pointer. Check its return value "
                "before using the variable; input handling for complete lines "
                "often uses `fgets` instead.\n\n```c\nint age;\n"
                "if (scanf(\"%d\", &age) == 1) {\n"
                "    printf(\"Age: %d\\n\", age);\n}\n```",
                ("variables-and-types", "variables-and-types"),
            ),
            (
                "operators",
                "Operators and expressions",
                "Use arithmetic and comparisons while noticing integer division.",
                "beginner",
                "Calculate with integer values",
                "Evaluate arithmetic and compare values of compatible types.",
                "C arithmetic follows operand types. Dividing two integers "
                "truncates the fractional part; convert an operand to floating "
                "point when that is not desired.\n\n```c\nint whole = 7 / 2;\n"
                "double fraction = 7.0 / 2;\nprintf(\"%d %.1f\\n\", whole, fraction);\n```",
                ("input-and-output", "input-and-output"),
            ),
            (
                "conditionals",
                "Conditional statements",
                "Choose branches using `if`, `else if`, and `else`.",
                "beginner",
                "Branch on a condition",
                "Write a comparison and group each branch with braces.",
                "C treats zero as false and nonzero as true. Use braces around "
                "blocks to make each branch clear and avoid accidental "
                "single-statement mistakes.\n\n```c\nint score = 7;\n"
                "if (score >= 10) {\n    puts(\"Ready\");\n"
                "} else {\n    puts(\"Practice\");\n}\n```",
                ("operators", "operators"),
            ),
            (
                "loops",
                "Loops",
                "Repeat instructions with `for` and `while` loops.",
                "beginner",
                "Count with a `for` loop",
                "Track initialization, continuation, and update in a C loop.",
                "A `for` loop initializes a counter, checks a condition, and "
                "updates it after each iteration. The loop body is skipped when "
                "the condition is initially false.\n\n```c\nfor (int i = 0; i < 3; ++i) {\n"
                "    printf(\"%d\\n\", i);\n}\n```",
                ("conditionals", "conditionals"),
            ),
            (
                "functions",
                "Functions",
                "Declare a function with parameter and return types.",
                "beginner",
                "Write and call a function",
                "Define a function that receives an integer and returns an integer.",
                "C function declarations specify return and parameter types. "
                "A function can return a value to its caller.\n\n```c\n"
                "int double_value(int number) {\n    return number * 2;\n}\n"
                "/* Call with: double_value(4) */\n```",
                ("loops", "loops"),
            ),
            (
                "arrays-and-strings",
                "Arrays and strings",
                "Use fixed-size arrays with zero-based indexes and mind their bounds.",
                "beginner",
                "Index an array",
                "Create an array and access a valid element by index.",
                "A C array has a fixed number of elements and does not check "
                "bounds for you. Valid indexes run from zero to one less than the "
                "array length. A C string needs room for its terminating `\\0`.\n\n"
                "```c\nint values[3] = {4, 5, 6};\nprintf(\"%d\\n\", values[0]);\n```",
                ("functions", "functions"),
            ),
            (
                "problem-solving",
                "Problem-solving and debugging",
                "Use compiler diagnostics and small reproducible cases to find errors.",
                "beginner",
                "Read a compiler diagnostic",
                "Compile with warnings and locate the source line mentioned in a message.",
                "Compile with useful warnings such as `-Wall -Wextra`. Read the "
                "first relevant diagnostic, inspect its file and line, and create "
                "a small input that reproduces the problem. A warning is not "
                "always harmless; understand it before dismissing it.",
                ("arrays-and-strings", "arrays-and-strings"),
            ),
        ),
    },
    {
        "code": "cpp",
        "name": "C++",
        "position": 3,
        "description": "A beginner path through compiling C++, typed values, "
        "console input, control flow, functions, vectors, and debugging.",
        "topics": (
            (
                "getting-started",
                "Getting started",
                "Understand C++ source files and the compile/run workflow.",
                "beginner",
                "Meet C++ and the compiler",
                "Learn that a C++ compiler builds source into an executable.",
                "C++ source is commonly saved in a `.cpp` file. A compiler "
                "translates it into an executable; for example, `c++ hello.cpp "
                "-o hello`, then run the executable. Compiler commands vary by "
                "operating system and toolchain.",
                None,
            ),
            (
                "first-output",
                "Output and your first program",
                "Recognize `main`, stream output, and the program's return value.",
                "beginner",
                "Print from `main`",
                "Use the standard output stream to display a message.",
                "A hosted C++ program starts at `main`. Include `<iostream>` "
                "and send text to `std::cout`; `\\n` starts a new line.\n\n"
                "```cpp\n#include <iostream>\nint main() {\n"
                "    std::cout << \"Hello, world!\\n\";\n    return 0;\n}\n```",
                ("getting-started", "getting-started"),
            ),
            (
                "variables-and-types",
                "Variables and basic types",
                "Use typed variables and type deduction for clear initial values.",
                "beginner",
                "Declare typed values",
                "Recognize integer, floating-point, and string values.",
                "C++ has types such as `int` and `double`; `std::string` is "
                "provided by `<string>`. `auto` can deduce a type from an "
                "initializer.\n\n```cpp\n#include <string>\n"
                "std::string name = \"Ari\";\nint lessons = 3;\n"
                "double ratio = 0.5;\n```",
                ("first-output", "first-output"),
            ),
            (
                "input-and-output",
                "Input and output",
                "Read console input with streams and check stream state.",
                "beginner",
                "Read a whole line",
                "Use `std::getline` for text that may contain spaces.",
                "`std::cin >> value` reads formatted values and usually stops "
                "at whitespace. Use `std::getline` to read a whole line of text; "
                "check whether the read succeeded.\n\n```cpp\n#include <iostream>\n"
                "#include <string>\nstd::string name;\n"
                "if (std::getline(std::cin, name)) {\n"
                "    std::cout << \"Hello, \" << name << '\\n';\n}\n```",
                ("variables-and-types", "variables-and-types"),
            ),
            (
                "operators",
                "Operators and expressions",
                "Use arithmetic and comparisons while distinguishing integer division.",
                "beginner",
                "Calculate with typed values",
                "Compare integer division with floating-point division.",
                "When both operands are integers, `/` performs integer "
                "division. Use a floating-point operand when you need a "
                "fractional result.\n\n```cpp\nint whole = 7 / 2;\n"
                "double fraction = 7.0 / 2;\n```",
                ("input-and-output", "input-and-output"),
            ),
            (
                "conditionals",
                "Conditional statements",
                "Select a branch using `if`, `else if`, and `else`.",
                "beginner",
                "Make a decision",
                "Write a comparison and use braces to group branches.",
                "An `if` statement runs its block when the condition is true. "
                "`else if` checks another case and `else` handles the rest.\n\n"
                "```cpp\nint score = 7;\nif (score >= 10) {\n"
                "    std::cout << \"Ready\\n\";\n} else {\n"
                "    std::cout << \"Practice\\n\";\n}\n```",
                ("operators", "operators"),
            ),
            (
                "loops",
                "Loops",
                "Repeat work with `for` and `while` loops.",
                "beginner",
                "Count with a loop",
                "Use a counted loop and inspect its condition and update.",
                "A counted `for` loop initializes a counter, tests a condition, "
                "and updates the counter after each iteration. A `while` loop "
                "repeats while a condition remains true.\n\n```cpp\n"
                "for (int count = 0; count < 3; ++count) {\n"
                "    std::cout << count << '\\n';\n}\n```",
                ("conditionals", "conditionals"),
            ),
            (
                "functions",
                "Functions",
                "Define a function with typed inputs and a return value.",
                "beginner",
                "Return a calculated value",
                "Write a function declaration and call it with an argument.",
                "A function signature states its return type and parameter "
                "types. `return` sends a value back to the caller.\n\n```cpp\n"
                "int double_value(int number) {\n    return number * 2;\n}\n"
                "// Call with: double_value(4)\n```",
                ("loops", "loops"),
            ),
            (
                "arrays-and-strings",
                "Arrays, vectors, and strings",
                "Distinguish fixed-size arrays from the resizable `std::vector`.",
                "beginner",
                "Use a vector",
                "Create a vector and read an element with a zero-based index.",
                "A built-in C++ array has a fixed size. `std::vector` from "
                "`<vector>` is a resizable sequence; `std::string` stores text. "
                "Use an index within the sequence's bounds.\n\n```cpp\n"
                "#include <vector>\nstd::vector<int> values{4, 5, 6};\n"
                "int first = values[0];\n```",
                ("functions", "functions"),
            ),
            (
                "problem-solving",
                "Problem-solving and debugging",
                "Use compiler warnings, a debugger, and small examples to investigate errors.",
                "beginner",
                "Investigate a compiler message",
                "Locate a diagnostic and test one small change at a time.",
                "Enable compiler warnings and read the first relevant diagnostic. "
                "Use its file and line location to inspect the code, then reduce "
                "the input to a small reproducible case. A debugger can step "
                "through the program and inspect variables.",
                ("arrays-and-strings", "arrays-and-strings"),
            ),
        ),
    },
)
