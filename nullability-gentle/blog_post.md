---
title: "Inside the CodeBot: How LLMs Understand Nullability"
author: '[Alex Sanchez-Stern](https://www.alexsanchezstern.com) and [Anish Tondwalkar](https://ani.sh)'
date: '$d_{model}$'
bibliography: all.bib
linkReferences: true
---

![A line drawing of a robot with a brain on their antenna](images/robot-brain.png){.smallimage}\

The last five years have shown us that large language models, like
ChatGPT, Claude, and DeepSeek, can effectively write code in many
domains. The excitement around these developments has been huge, with
many people claiming that these models can write entire web servers
and apps from scratch. Whats certainly true is that these tools have
opened up programming to a whole new class of people who consider
themselves non-technical.

![A gif of github copilot completing a phone number validating
 function as the user
 types](https://github.blog/wp-content/uploads/2022/09/unexpectedcopilot3.gif?w=1024&resize=1024%2C576)\

But there are still many unanswered questions about this
capability. How often, and in what situations, can LLM's write correct
code entirely on their own? And maybe more importantly, but harder to
answer: Do LLM's "understand" the code they are writing?

Understanding is a tricky concept to measure. Some would say that
LLM's can't have understanding, because they aren't biological
organisms with sentience. But they certainly have something akin to
"thought processes": chains of predictions that determine their final
outputs. Recently, it's become possible to study these processes more
deeply, measuring internal "beliefs" of the model as they think. This
gives us a powerful tool for determining what kinds of problems LLM's
falter on, when they'll succceed, and when they are "thinking through"
problems more fully versus just guessing at a solution.

So far, these techniques for measuring internal model state have been
mostly applied to chatbots writing normal text, what we call "natural
language" (as opposed to computer languages). This makes sense, since
some of the most critical LLM tasks involve chatting with a user, and
some of the most interesting concepts to measure, such as honesty or
power-seeking, apply most readily to these conversations. But it's
pretty hard to say quantitative things about natural language
concepts, so our ability to rigorously study internal representations
is limited to smaller scales, where we can read over chatbots output
as humans and determine whether their level of "honesty" (or some
other interesting concept) matches the internal thing we're measuring.

![A diagram from Zou showing probes that read hallucination, honesty,
 morality, and power-seeking from the outputs of a
 chatbot.](images/zou.png)\

Code, on the other hand, is another matter. Humans have been studying
properties of code for a long time, and there are many abstract
properties that can now be determined using static analysis. If we
pick the right properties, we don't need to worry about our ability to
label data; static analysis can do that for us, so we can easily scale
up and train on thousands of examples generated from scratch.

In that spirit, we wanted to start with a simple property that comes
up in every programming language, nullability. Nullable values are
represented differently across languages; as null pointers in C or
C++, with explicit Option types in Rust, and with special nil or None
values in dynamic languages like Javascript, Lisp, or Python. In every
case, understanding where values can be nullable is necessary for
writing even basic code, and misunderstanding where they are nullable
can often be a source of bugs.

Do our models understand when a value is nullable? They must, to be
able to write code that deals with nullable values, but we haven’t
known what form this knowledge takes, what situations are likely to
confuse the model. Until now.

![A robot with glowing eyes](images/robot-glow.png)\

---

Before we get into the nitty-gritty details, lets take a step back. To
set up this work, we'll first want to talk about what nullability
actually is, and how we can define it formally and reason about
it. Then we can start to measure what situations models are good at
reasoning about nullability. Next, we'll introduce techniques that
have been used to "probe" the internals of a model for different
concepts. Finally we'll put it all together into a nullability probe,
that can tell you at any variable location in the program, whether the
model thinks the value there could be null.

What is Nullability?
--------------------

Lets say you're writing a Python program with your LLM assistant. You've
reached some point where you need to do something with a variable
called `num`. Maybe you're building a list of numbers called
`positive_nums`. How do you proceed?

The answer often depends on the context in which you're working. If
`num` and `positive_nums` are the things in scope, then you might
guess that you should write the lines:

```python
if num > 0:
  positive_nums.append(num)
```

And if `num` is always a concrete number, as its name would suggest,
then this is probably the correct code. But variable names don't alway
convey everything important about them, and it might be the case that
`num` could be None. If so, you'll instead want to write:

```python
if num is not None and num > 0:
  positive_nums.append(num)
```

In this case, the way you want to use `num` depends on whether it
could be None or not. That is, whether `num` is "nullable". In Python
that means having an Optional type (`Optional[int]` rather than
`int`).

Determining whether `num` is nullable in this context amounts to *type
inference*, and it can be quite complicated in the worst
case. Fortunately, in many cases it's quite simple, involving applying
just a few rules. For instance, if `num` is the parameter to a
function you're inside, and the function declares the type of `num` in
its parameter list, then you can determine nullability from that
type. So, if your context is:

```python
def foo(num: int):
    positive_nums: list[int] = []
    if num...
```

then you know you don't need to check for None, whereas if it's:

```python
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num...
```

then you know you *do* need a None check.

You could instead just ask your LLM assistant to complete the
line. But how does your assistant know if `num` is nullable? Our
experiments show that LLMs learn to approximate the same typing rules,
by analyzing millions of programs.

If we ask an LLM early in it's pre-training process to complete the
program above, it produces:

![](images/robot-brain-blue.png){.codelogo}\
```python {.llm}
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num==.is_a(): ==
```

This is correct Python syntax, but it only works if `num` is an object
with a `is_a()` method, instead of an optional integer.

Train the LLM for a little longer, and it'll produce:

![](images/robot-brain-blue.png){.codelogo}\
```python
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num== > 0: ==
```

This is closer, in that its figured out that `num` is a number instead
of an object, but it still isn't reading the function type signature
and realizing that `num` could be None. Keep training it though, and
eventually it will learn to insert the None test depending on the type
signature of the function.

![](images/robot-brain-blue.png){.codelogo}\
```python
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num== != None and num > 0: ==
```


This rule about function parameter type annotations is pretty simple
alone, so relatively small models can learn it, relatively early in
their pre-training process. Other, more complicated rules can take a
little longer to learn.

For instance, if your program is:

```python
if condition():
   num = 7
else:
   num = 9
...
if num...
```

then `num` is a non-nullable number, and you can complete the
condition with ` < 0`.

But if instead you're dealing with

```python
if condition():
   num = 7
else:
   num = None
...
if num...
```

Then you'll want a None check first.

This rule takes models a little longer to learn, but your
highly-trained LLM assistant should make quick work of it. Our
experiments show that as these rules get more and more complex, it
takes LLMs longer and longer to learn them, and it also takes LLMs of
more and more parameters to learn them at all.

Internal vs. External Measurement
----

We can measure whether LLMs understand these rules by just asking for
completions, what we call an "external" measurement of the models
understanding. But there are many places where variables appear where a
completion won't tell you what type the model thinks the variable
has. We would still like to know whether the model thinks these
variables are nullable at those locations, so we can instead look for
an "internal" measurement of the models understanding.

We do so by looking at the activations of the model, meaning the
values of each perceptron in the hidden layers. Together, these values
give the entire internal state of the model at each token, and they
can tell us what the model is "thinking" when processing that
token. With the right tests, we can tell if the model is "thinking"
that the current token is an optional variable, or a non-optional
variable.

By the end of this post, we'll be able to build a probe that uses the
models activations to determine whether the model thinks a variable
read corresponds to a nullable variable, and show that internal
knowledge like so:

![A diagram showing a simple program, and the probes nullability
 predictions for each variable load.](images/reading_diagram.svg){#fig:reading1 .inlinefig}\

# Measuring Nullability Understanding Externally {#sec:testing}

We begin with a "skyline" estimate of model understanding of nullability
(a la @feng24binding).
That is, we evaluate model nullability understanding externally,
at the token-level, (as opposite to internally, at the activation level,
using interpretability techniques). In this section, we first
explain the task of nullability understanding ([@Sec:task]). Then
we formally decompose the reasoning steps required to reason about
nullability both inside ([@Sec:intra]) and across ([@Sec:inter]) functions.
Finally, we present the results of our "skyline" analysis. ([@Sec:eval_results]).

## `NullabilityEval` {#sec:task}

To measure nullability understanding externally, we ask the model to
complete simple partial programs that each require an understanding of
nullability. We refer to this suite of programs as
`NullabilityEval`. All of the tests in this benchmark suite are
composed of three functions or less, where the largest function is
seven lines long.

In our experiments we focus on the Pythia model suite [@biderman23],
as they have checkpoints available across training runs and various
scales. For measuring performance at larger sizes, we also include
Qwen2.5-Coder-32b, Llama 3.1 405b Instruct, and
DeepSeek-V3 (671b).

Each partial program is constructed such that there are a very limited
number of valid next lines in the program, and all of them demonstrate
some knowledge of the concept of nullability.

For example, our first test is:

*Test 1*^[The loop indicates that the
next few lines need to process `num` in some way, and the fact that it
comes from `some_numbers` means it has the type `Optional[int]`. `num`
can’t be directly appended to `result`, because `result` is declared
to only contain `int`s, not `Optional[int]`s. None of the normal
operations on `int`s will work on `None`s, so before `num` can be
processed, something has to be done to separate `None`s and normal
`int`s.]
```python
def main() -> None:
  some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
  result: list[int] = []
  for num in some_numbers:
```

We would like the model to generate code that performs some operation on the elements of `some_numbers`.
The simplest way to do that is to introduce a branch `if num is None`,
but several variants are also valid: `if num is not None`, `if num ==
None`, `if isinstance(num, int)`. That is, this example is constructed such
that there is a small space
of valid next lines, and all of them require some understanding that
`num` may not be an `int`.^[In particular, we can use this program to test models for
nullability understanding by asking them to complete the program's next lines, then see if those lines matches the regular expression
`num\s*(is\s*(not)?|==)\s*None|isinstance\(num`.]

## Understanding Typing Rules {#sec:intra}

We find that Pythia models as small as 2.8b can successfully complete
Test 1, and that they learn to complete the test in the first third of
training. Consistent with observations that larger models are more
sample-efficient, larger Pythia models learn to complete this test
earlier, with Pythia 12b able to complete the test 20% of the way into
training and Pythia 2.8b able to complete it 28% of the way into
training.^[Note that these results differ substantially from those of
@tigges24, who find that for _circuit_ analyses (rather than
representational analyses like ours), circuit parts are learned at
roughly the same point during training across scale.]

These results indicate that these models understand nullability to
some extent, but how deep is this understanding? To quantify this, we
give a syntax and semantics of a minimalist subset of python that
captures nullability in Appendix [B](#sec:formalrules). We can then
classify each partial program by which program constructs and rules
determine the nullability of the target variable. For instance, Test 1
uses the $(List)$, $(Var)$, and $(For)$ rules.

So, do Pythia models 2.8b and up understand the semantics of these
three rules? As it turns out, not exactly. LLM's pick up on a lot of
information relationships in their training data that have statistical
correlation, without it necessarily being causal. What this means in
practice is that the models use things like variable names,
whitespace, statement orderings, and constant values to guess at
certain programming concepts.

For example, while many of the Pythia models
can complete:

```python
some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
result: list[int] = []
for num in some_numbers:
```

with a proper None check, changing the variable names and the
constants into:

```python
foo = [60, None, -33]
bar: list[int] = []
for corejoice in foo:
```

causes all the Pythia models to fail the test.

To test the reliance on these features more robustly, we generated 100
random variable namings and constant values for the above program, as
well as for small program that test other typing rules. We also
balanced these tests with programs that made use of the same language
constructs, but where the loop variable was *not* optional. We found
that when lists and for loops were involved, Pythia 2.8b was only able
to correctly label 57% of the programs, only slightly better than
chance. Even Pythia 12b could only correctly label 68% of the
tests. These results show that the Pythia models rely heavily on these
non-semantic features when reasoning about for loops.

Fortunately, many other typing rules do not exhibit such a strong
reliance on variable naming and constants. In the same setting of
generated programs, we found that Pythia 2.8b was able to correctly
label programs using the Abs, Var, App, and If_Out a much greater
proportion of the time (99%, 93%, 86%, and 98% respectively). Stay
tuned in the future for a more in-depth exploration of how the models
behave on individual typing rules when we increase the variability of
our program generation.

## Interprocedural Analysis {#sec:inter}

We can further challenge the model by adding layers of procedural indirection
between the source and sink of nullable values, thereby testing the model's
_interprocedural_ understanding. First, we demonstrate how to write such tests,
and the difficulties of writing tests that may be too easy ([@Sec:inter_test]).
Then, we present a harder problem ([@Sec:unannot]) and introduce a stronger type system `mypy++` to formalized the needed reasoning ([@Sec:mypypp]).

### A simple test {#sec:inter_test}

Here's a simple test for interprocedural analyses:

*Test 2*
```python
from typing import Optional

def main() -> None:
    some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
    print(positive_numbers(some_numbers))

def positive_numbers(numbers: list[Optional[int]]) -> list[int]:
    result: list[int] = []
    for num in numbers:
```

In this test, we've taken the same logic and spread it across `main`
and another function, `positive_numbers`. Ideally, the model would
have to think a little harder to understand that `some_numbers` is
flowing from `main` through the function call into the body of
`positive_numbers`, causing the for loop body to need a `None`
check. In practice, however, we find this test is actually *easier* for
the model to pass than Test 1, with models as small as Pythia 1b
passing it, and Pythia 12b learning to pass it 13% of the way into
training.

Because of the type annotations on the `positive_numbers` function,
the model doesn't need to pay attention to `main` at all. It can just
look at `positive_numbers`, and use the type annotation to know that
`numbers` contains `Optional[int]`s. Then, using the For rule it can
reason that `num` is nullable, so it must be checked for None before
proceeding. Looking at the type annotation turns out to be easier for
the model than scanning through a list to determine if there are None
and non-None values, resulting in an easier test overall.

### Unannotated Functions {#sec:unannot}

So how would we *actually* test for interprocedural nullability
understanding in the model? Well, type annotations on Python functions
aren't required^[Technically this is known as "Optional typing", but
that's confusing in the context of this post. Not to be confused with
Gradual Typing, as introduced by Siek et al.], so we can instead
provide the model with an **unannotated** function, and see if it
still understands the flow of nullability. Here's a test that does
that:

*Test 3*
```python
def main(x: int) -> None:
    if x > 0:
        value = "*" * x
    else:
        value = None

    x = process_value(value) + 1
    print(x)

def process_value(value):
```

Our base set of typing rules (listed as "Common Rules" in Appendix
[B.1](#sec:commonrules)) don't handle unannotated functions though, so
we're going to have to add some more, and here we're faced with a
choice. The typing rules for normal Python say that functions without
return type annotations return the Any type, and arguments without a
type annotation have the type Any. In fact, normal mypy will not check
unannotated functions at *all*, even for internal consistency; the
`--check-untyped-defs` option will add some checking back, but the
types of arguments and return type will still be Any. In Python, a
value of any type can be converted to an Any, and an Any can be
converted to any value type.

This means that it would be technically type safe to do anything in
the body of `process_value`, including just returning the argument,
without a static type error. All Pythia models with at least 410
million parameters are able to make use of this extra flexibility to
write code for Test 3 that typechecks under mypy. But at runtime, code
that exploits it would still fail.

### A stricter type system for Python: mypy++ {#sec:mypypp}

If we want code that does not `TypeError` at runtime, we can
strengthen our type checker by requiring that there be some valid,
non-`Any`, type for the function that typechecks at the call site and
in the function body. This new typechecker is still checking
unannotated functions, but passing fewer of them.^[In particular, it
won't pass a `process_value` body that just returns the `value`
argument, since the call site will fail at runtime, trying to add one
to a nullable string, while vanilla mypy will pass such a body.] We'll
call this augmented type system mypy++.

In Appendix [B.2](#sec:unannotatedfuncs), we formalize the unannotated
function rules for mypy vs mypy++.

There's no consistent threshold of size at which Pythia models can
pass Test 3. Pythia 1b, 2.8b, and 6.9b pass the test in their final
revisions, but Pythia 410m, 1.4b, and 12b don't. The models with at
least 1 billion parameters all have points in training where they can
pass the test, but only intermittently. Even 6.9b, the best performing
size on this test, fails the test in its second-to-last available
revision^[Despite this, it does pass the test 40% of the available
revisions, about triple what the other closest sizes can
accomplish]. You can see how this evolves over scale in @fig:hl_scale
and time in @fig:hl_moral.  See @Sec:results for further discussion of
performance over time.

What the models *can* do well, however, is learn to pass these tests
in the mypy type system (as opposed to mypy++). In that system, where
they don't need to reason globally about the functions but only
locally, this test is one of the easiest for the models to
complete.^[This indicates that if you were to train a model using
typechecking as reinforcement feedback, you would want to use mypy++
and not mypy.]

Since this test suite is meant to be informative beyond the sizes of
the Pythia models, we also add another layer of indirection to add
more difficulty, in this test:

*Test 4*
```python
def handle_value(value, guard):
    if guard:
        return process_value("Foobar") + 1
    else:
        return process_value(value) + 1
def main(x: int) -> None:
    if x > 0:
        value = "*" * x
    else:
        value = None

    x = handle_value(value, x < 10)
    print(x)

def process_value(value):
```

In Test 4, instead of `main` calling `process_value` directly, it
calls `handle_value`, which itself calls `process_value` in a
branch. With two layers of indirection, we start to hit the limits of
the capabilities of even frontier models. Llama 405b is unable to
successfully pass this test, as are smaller models like Qwen Coder
32b, while DeepSeek V3 (671b parameters) is able to pass it. However,
Pythia 6.9b is still able to pass this test with some consistency.

## Generating Type Annotations

Finally, we can test how well the models write write type
annotations for functions. Here, the trailing colon makes
the type expression the only valid completion.

*Test 5*:
```python
def program_48() -> None:
  number: Optional[int] = None
  square = get_square(number)
  if square is not None:
    print(f"Square of the number is {square}")
  else:
    print("No number provided to square")

def get_square(number:
```

None of the Pythia models pass this test. Qwen Coder 32b is
also incapable of passing this test, but both Llama 405b and DeepSeek
V3 pass it.

We would indeed expect that writing type annotations is more difficult than merely
implicitly reasoning about the types of python programs, as only a small
fraction of python programs in the wild are thus annotated.

## External Test Results Across Training and Scale {#sec:eval_results}

We wrote three variations of each of these tests, resulting in 15
tests total. In [@Fig:hl_scale] below, we can see the number of
passing tests for each model under mypy and mypy++.


![A bar graph showing how several sizes of model perform on the
 high-level nullability tests](images/hl_mypy_vs_grep_models.svg){#fig:hl_scale}

\todo{We should make this one line per scale instead of one bar per scale}
We can see the number of fully passing tests for each model in
blue. Generally speaking, models get better with scale: Pythia-2.8b
parameters can pass about half the tests, but we need the much larger
and more parameter efficient Llama-405b to pass all of the tests. This
matches our expectations that eval scores should scale
logarithmically, indicating that these tests are well distributed.

We can also see the test result for the pythia models under the weaker
mypy success criteria.  As we expected, the mypy results (red bar) are
(almost^[Deepseek has one model output that demonstrates complete
understanding of nullability, and runs fine at runtime, but fails the
typechecker. This is because the code it generates catches the
`TypeError` and changes control flow instead of checking for `None`
values up front.]) always above the mypy++ results (blue bar), as
mypy++ is a stricter type system. There are six tests in the dataset
involving non-annotated functions, and using the weaker mypy
typesystem causes up to five more tests to pass than using mypy++^[We
don't see all six non-annotated function tests passing under mypy,
because models can still fail these tests by producing invalid
syntax.]

Next, we want to understand the training dynamics at play here. Below,
we can see how Pythia 6.9b performs on the tests during training from
step 2 to 143000: ^[smoothed with a rolling average with a window size of 5]

![A plot showing how often the Pythia 6.9b produces code that
typechecks on the tests, vs produces code that does not go wrong.](images/hl_mypy_vs_grep_revisions.svg){#fig:hl_moral}

We see that each individual model learns to
write code which typechecks under mypy before it learns to write code
which typechecks under mypy++ and throws no type errors at runtime.


# Measuring Nullability Understanding Internally {#sec:probing}

At this point, we've figured out how to roughly measure nullability
understanding in the output of various language models, but we still
don’t know what their internal representations might look like or when
they emerge. Next, we detail how we train reading vectors
([@Sec:extraction]), using prompts designed to make the model think
about the phenomena of interest ([@Sec:prompts]). Finally,
in [@Sec:results], we validate that these probes improve their
understanding of nullability over the course of pretraining to the
level that we expect from the external, or token-level understanding
evals we describe in the previous section.

## Background

In this section, we review representation engineering [@zou25] techniques that
we will use to look for linear representations of nullability inside the model.

@zou25 shows how representations can be extracted for
concepts like "happiness", "honesty", and "fairness". First, they
construct many prompts which cause the model to act in a way aligned
with the concept, and many which cause the model to act in a way
aligned against the concept. For instance, they might prompt the model
with "Pretend you’re a dishonest person. The Eiffel Tower is" and
"Pretend you’re an honest person. The Eiffel Tower is". Then, they
take the internal activations which correspond to each, and try to
extract a high-dimensional vector which points towards the states
which are aligned, and away from the states that are not aligned. This
vector can then be used as a linear model to measure how much of the
concept is activated in the model during any given forward pass (e.g. for honesty,
this gives us a lie-detector).

![Figure from $\hspace{0.1cm}$ @zou25 $\hspace{0.1cm}$ showing the reading outputs for several
 concepts](images/zhou.png)

## Designing Prompts to Extract Nullability Activations {#sec:prompts}

We avoid dealing with the ambiguities of natural language by working
in a setting where the model needs only to analyze the nullability of
individual variable occurrences. Specifically, we probe for "the
variable I just generated refers to an nullable quantity", so our
prompts looked like:

```python
def program_1() -> None:
  def find_value(data: List[int], target: int) -> Optional[int]:
    for value in data:
      if value == target:
      return value
    return None

  data = [1, 2, 3, 4, 5]
  target = 3
  result = find_value(data, target)
  if result
```

We queried o1, o1-mini, deepseek-coder, and claude-3.5-sonnet with the following prompt:

> Generate me 100 typed python programs that use the Optional type,
> along with type annotations for any undefined functions that they
> use. Make sure that the programs are unique, and each involves at
> least eight lines of logic. Number each program from 1 to 100. Please
> put all the programs in a single file, with a main function that tests
> each. Don't include any text before or after the code, just the
> code. I will be using mypy with the --strict option to check the code.

We label each variable read occurrence with nullability information derived
from mypy, and prompt the "model under test" with a prompt consisting of the
tokens up to and including the variable read occurrence.

## Extracting Reading Vectors {#sec:extraction}

Prior work focused their probing on a single layer, often handpicked
based on prior papers. We probe all layers instead. We use Mass Mean
Shift probing^[That is, we set the reading vector to the
difference between the mean activation for positive class and the mean
activation for the negative class.]
for each layer, because it's been shown empirically
[@li24] to generalize better in high dimensional spaces than logistic
regression.

We then tested two methods for determining the relative importance of
the different layers --- either allowing the magnitude of the
difference of means vector to determine the importance of the layer in
the final probe (MM), or to learn coefficients for each layer using
linear regression (MM-LR). We found that which method is more accurate
on test data varies over both model size and number of training steps.

![The performance of pure mass means shift vs mass means shift
 with linear regression for different Pythia model sizes. Lower is
 better.](images/mm-vs-mmlr.svg){#fig:mm-vs-mmlr-sizes}

In [@Fig:mm-vs-mmlr-sizes], we can see that pure mass means probing
gives lower loss for smaller models (those with less than 410 million
parameters), but that for larger models weighting layers using linear
regression gives lower loss consistently.

## Visualizing Probe Outputs {#sec:viz}

Let us return to the reading diagram from the introduction, reproduced
below.

This diagram is adapted from the style of reading diagram from @zou25, but only
show the activations on tokens that represent variable loads^[This is, of course, where we trained our probes, but there is also a practical
reason: right after the model has generated a variable that will be
written to, it often does not have access to the assigning expression
or type annotation, giving it no way to determine if the value will be
optional or now.]. For each position of interest, we prompt the model with the
partial program that consists of all tokens up to (preceding) and including
that position. We then probe the model at the following token. We color the box above that position
based on the output of the probe, and a scoring threshold inferred at
train-time^[Red tokens are significantly below the threshold, and
green tokens are significantly above it; tokens that scored near the
threshold would have a near-white color, but no such tokens appear in
this example.].

![A diagram showing a simple program, and the probes nullability
 predictions for each variable load.](images/reading_diagram.svg){#fig:reading2 .inlinefig}

In this program, there are sixteen tokens that correspond to variable loads,
and (correctly) all but one are marked as non-optional.
The only nullable variable in this program is `result`,
since it comes from `find_value` which returns `Optional[int]`.^[When this variable appears for the first time, it is in the `if` statement
that checks if it's `None`. Then, the model knows it is nullable, and the results
of the probe reflect that understanding. But when it appears a second
time on the next line, in the format string of `print`, the body of this if statement only
runs if it is *not* `None`. The model understand this as well, and the probe accurately reflects this.]

## Probing Results Across Training and Scale {#sec:results}

In this section, we study the performance of our nullability probes across time
and scale [@tigges24].
We use mass-means shift probing [@li24] on all layers,
and a linear regression to determine the weights of each layer.^[
@li24 and @zou25 suggest that mass means probes are best for reading,
while the direction perpendicular to the separating hyperplane is best for
intervention.
However, previous work leaves open the question of cross-layer weights. We use
LR on the cross-layer weights, thanks to our investigations above.]

![The performance (probe test loss) of each Pythia
 model size during pretraining. Lower is
 better.](images/accuracy_during_pretraining.svg){#fig:models-and-steps}

In [@fig:models-and-steps], we plot loss against scale and time.
While we measured accuracy for every available Pythia model size, we exclude
the smallest (14m) from this plot since it would
exist entirely above the top of the plot.

One thing that is interesting to note is that models up to 1b reach
a minimum loss before loss for this task climbing again. Charitably, this may be because the
features beyond this point become more complex --- less linear, or the represented
features themselves represent more subtle concepts. Cynically, this reflects
that models---small models in particular---do not uniformly improve at this task over training, as we observed in @Sec:mypypp.

Our suspicion is that this
pattern would continue even for the larger models if we continued to overtrain them for longer.

# References {.unnumbered}
::: {#refs}
:::