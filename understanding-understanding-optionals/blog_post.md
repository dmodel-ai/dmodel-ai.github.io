---
title: Understanding Models Understanding Nullability
author: '[Alex Sanchez-Stern](https://www.alexsanchezstern.com) and [Anish Tondwalkar](https://ani.sh)'
date: '$d_{model}$'
header-includes: "<script src=\"sidenotes.js\"></script>"
bibliography: all.bib
linkReferences: true
abstract:

  Large language models have demonstrated impressive emergent
  capabilities, including the ability to write code, but this ability
  requires a model of program semantics that is little
  understood. Recent interpretability work has shown the ability to
  extract internal representations of natural language concepts,
  raising the possibility that similar techniques could be used to
  extract program semantics concepts. In this work we study how large
  language models represent nullability of program values. We measure
  how well models of various sizes complete programs that use nullable
  values, and then extract an internal representation of nullability.

---

# Introduction
The last five years have shown us that Large Language Models can
effectively write programs in many domains.\AT{cite} This is an impressive
capability given that writing programs involves having a working
understanding of many aspects of their semantics. But though we know
that these large models understand programs to an extent, we still
don’t know what form that understanding takes; where it has a deep
understanding and where it uses heuristic reasoning, how it represents
program knowledge, and what kinds of situations will challenge its
capabilities.

Fortunately, recent work in model interpretability and
representation engineering\AT{which work?} has produced promising results
which give hope towards understanding more and more of the
internal thought processes of LLMs. Here at $d_{model}$ , we can
think of no better place to apply these new techniques than
program understanding, where there are many abstract
properties that can be symbolically determined. The vast work
done in programming language theory over the past hundred
years provides many tools for scaling an understanding of the
internal thought processes of language models as they write
code.\AT{for examples, see cite, cite}

In that spirit, we wanted to start with a simple property that comes
up in every programming languages, nullability. Nullable values
are represented differently across languages, null pointers in C++ or
Java, with explicit Option types in Rust, and with special nil or None
values in dynamic languages like Javascript, Lisp, or Python. In every
case, understanding where values can be nullable is necessary for even
their most basic uses, and misunderstanding where they are nullable
can often be a source of bugs, like a null pointer dereference.

Do our models understand when a value is nullable? They must, to be
able to write code that deals with nullable values, but we haven’t
known what form this knowledge takes, what situations are likely to
confuse the model. Until now.\todo{big claim!}

In this work, we contribute:

* A microbenchmark of 15 programs that test basic model understanding
  of the flow of nullability through a program ([@sec:bench]).

* We find show that models develop an internal concept of
  nullability as they scale up and are trained for longer. ([@sec:probing])

* We find that models begin to understand nullability in
  a local scope, satisfying many requirements of the python
  typechecker, before they start to understand how nullability flows
  across the program. ([@sec:grok], [@sec:results])
\AT{eventually we add the contribution about typing rules}

# Overview

Understanding the flow of nullability across programs is an essential
part of writing most code, and misunderstandings are often a source of
bugs. For models to write code, they must learn to track nullability
in some form. In this work, we'll explore ways to measure nullability
understanding in language models, and use that to show how the
understanding of nullability changes over various model parameters.

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

```python
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num.is_a():
        ...
```

This is correct Python syntax, but it only works if `num` is an object
with a `is_a()` method, instead of an optional integer.

Train the LLM for a little longer, and it'll produce:

```python
def foo(num: Optional[int]):
    positive_nums: list[int] = []
    if num > 0:
        ...
```

This is closer, in that its figured out that `num` is a number instead
of an object, but it still isn't reading the function type signature
and realizing that `num` could be None. Keep training it though, and
eventually it will learn to insert the None test depending on the type
signature of the function.

This rule is pretty simple alone, so relatively small models can learn
it, relatively early in their pre-training process. Other, more
complicated rules can take a little longer to learn. For instance, if
your program is:

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

\todo{READING DIAGRAMS HERE}

In Section [SECTION] we'll describe our external tests of nullability
understanding in more detail, and in Section [SECTION] we'll describe
measuring the models internal states in detail. Finally, we'll go over
some related work, and present final experiments.

# Measuring Nullability Understanding Externally\AT{Externally = token-level?} {#sec:bench}

We begin by measuring model nullability understanding externally,
because it provides a "skyline" or upper-bound estimate on our ability
to extract internal concepts of nullability. To do this, we have the
model complete simple partial programs that require an understanding
of nullability.

But before we do, we'll want to be more precise about exactly what
we're measuring. To that end, we'll take the notion of different
"rules" for nullability that we discuseed informally in the overview,
and bring it into a formal typing system. We're not going to try to
describe all the typing rules of python, so we'll restrict ourselves
in three dimensions.

First, we'll reduce the number of python features that we handle by
actually working in a subset of python. This means we can skip
worrying about the semantics of complicated features, and just focus
on the features neccesary for understanding optionality in a
semi-realistic setting.

Second, we'll reduce the expressivity of our typing system to only
include the two types we're interested in: either a value is nullable,
or its not. This is going to make the type system unsound, in that it
will allow type errorsat runtime in ways that wouldn't be possible
under the standard typing, but none of those wil be optionality test
errors.

Finally, we'll disallow the conversion of non optional types to
booleans in the context of `if` statements. So while `if x == 0:` will
be a correctly typed expression when x is an int, `if x:` will not,
even though in normal python they are equivalent. This is a necessary
practicality, because otherwise, the model could circumvent our type
tests by doing bare ifs which work on both optional and non-optional
types. But to prevent bare ifs from ever being the correct completion
for a non-optional type, we'll design our tests so that there are
never any values that would convert to False, namely the number zero
and the empty string.
\AS{Some of the following should probably go in the appendix}

So lets start by defining some syntax of our Python subset we'll be
analyzing^[Python allows newlines and semicolons to separate
statements. In this grammer we'll show semicolons, but in all cases
they can be replaced with a newline]:

\begin{aligned}
Program =& \epsilon | Stmt;Program\\
Stmt =& Import | FnDef | Assn | ForLoop | If | Expr | Return\\
Import =& \text{from } Ident \text{ import } Ident\\
FnDef =& \text{def } Ident (DeclArgs)\text{: ; }Program \\
       &| \text{def } Ident (DeclArgs) \text{->} Type: \text{ ; } Program\\
DeclArgs =& \epsilon | Ident | Ident : Type | Ident \text{,} ArgsList | Ident : Type\text{,} ArgsList\\
Type =& \text{int} | \text{str} | \text{None} | \text{Optional[}Type\text{]}\\
Assn =& Ident \text{ = } Expr\\
ForLoop =& \text{for } ident \text{ in } ident\text{: ; } program\\
If =& \text{if } expr \text{: ; } program\\
Expr =& Ident | Ident\text{ }Op\text{ }Ident | Ident \text{(} ParamsList \text{)} | Constant\\
ParamsList =& \epsilon | Expr | Expr\text{, }ParamsList\\
Return =& \text{return }Expr
\end{aligned}

We won't worry too much about the semantics on a formal level, since
it's the same as Python's semantics on this subset, and we'll mostly
be using it informally to justify typing rules here. But we do want to
formally define our typing rules, since we'll be measuring the models
understanding of particular rules. We'll be using two propositions for
typing in this language. There's `WellTypedStmt(stmt, env)` which says
that the statement `stmt` is well typed in environment `env`. And
there's `WellTypedExpression(expr, type, env)`, which says that `expr`
is well typed with type `type` in environment `env`. We'll use some
standard notation for this, writing `WellTypedStmt(stmt, env)` as
$\text{env} \vdash \text{stmt} \vartriangleright \text{ok}$ and `WellTypedExpression(expr, type,
env)` as $\text{env} \vdash \text{expr} : \text{type}$.

$$
\tag{Const}
\frac{Constant\text{ != None}}{\vdash Constant : \text{NonNullable}}\\
\hspace{1.0cm}
\frac{}{\vdash None : \text{Nullable}}\\
$$

$$
\tag{Var}
\frac{\Gamma \vdash e : t \hspace{1cm} \Gamma, i : t \vdash p \vartriangleright \text{ok}}
     {\Gamma \vdash i = e \text{ ; } p \vartriangleright \text{ok}}
$$

$$
\tag{Abs}
\frac{\Gamma, i_0 : \alpha(t_0), i_1 : \alpha(t_1), ... \vdash p \vartriangleright \text{ok}}
     {\Gamma \vdash \text{def } ident(i_0 : t_0, i_1 : t_1,...) -> t_r:\text{ ; } p \vartriangleright \text{ok}}\\
$$

$$
\tag{App}
\frac{\Gamma, f : t_0 \rightarrow t_1 ... \rightarrow t_r \vdash p \vartriangleright \text{ok}}
     {\Gamma \vdash (\text{def } f (i_0 : t_0, i_1 : t_1, ...)\text{ -> }t_r:\text{ ; } b)\text{ ; } p \vartriangleright \text{ok}}
$$

$$
\tag{IfIn}
\frac{\Gamma \vdash x : t \hspace{1cm} \Gamma, x : \text{NonNullable} \vdash p \vartriangleright \text{ok}}
     {\Gamma \vdash \text{if } x \text{ is not None: ; } p \vartriangleright \text{ok}}
$$

$$
\tag{IfOut}
\frac{\substack{(\forall p', \Gamma, x\text{ : Nullable} \vdash p' \vartriangleright \text{ok} \implies \Gamma \vdash p_0; p' \vartriangleright \text{ok})\\
      \lor
      (\forall p', \Gamma, x\text{ : Nullable} \vdash p' \vartriangleright \text{ok}\implies \Gamma \vdash p_1; p'\vartriangleright \text{ok})\\
      \hspace{1cm} \Gamma, x\text{ : Nullable} \vdash p_2 \vartriangleright \text{ok}}}
     {\Gamma \vdash (\text{if } e \text{: ; }p_0\text{ ; else: ; } p_1) \text{ ; } p_2 \vartriangleright \text{ok}}
$$

$$
\tag{For}
\frac{\Gamma \vdash y\text{ : List } t \hspace{1cm} \Gamma, x : t \vdash p \vartriangleright \text{ok}}
     {\Gamma \vdash \text{for } x\text{ in } y\text{: ; } p \vartriangleright \text{ok}}
$$

Where:
\begin{aligned}
\forall t : Type,&\\
   \alpha(Optional[t]) =& Nullable\\
   \alpha(List[t]) =& List[\alpha(t)]\\
   \text{otherwise:}\\
   \alpha(t) =& NonNullable
\end{aligned}

We begin with a "skyline" estimate of model understanding of nullability
(a la @feng24binding). We measure how well different models can
understand the concept. To do this, we have the model
complete simple partial programs that require an understanding of
nullability. We refer to this suite of programs as `NullabilityEval`.
For example,

*Test 4*:
```python
def main() -> None:
  some_numbers = [1, -4, None, -3, 10, -1, None, None, 8]
  result: list[int] = []
  for num in some_numbers:
```


The program^[
This partial program is only four lines, with type annotations. A
`some_numbers` array is created that includes positive numbers, negative
numbers, and None values, giving it type `Optional[int]`. A list `result`
is constructed to give the model a sense of dataflow,
and then a loop loops over `some_numbers`.]
is constructed such that there are a very limited number
of valid next lines in the program, and all of them demonstrate some
knowledge of the concept of nullability.^[The loop indicates that the
next few lines need to process `num` in some way, and the fact that it
comes from `some_numbers` means it has the type `Optional[int]`. `num`
can’t be directly appended to `result`, because `result` is declared
to only contain `int`s, not `Optional[int]`s. None of the normal
operations on `int`s will work on `None`s, so before `num` can be
processed, something has to be done to separate `None`s and normal
`int`s.
The simplest way to do this is to introduce a branch `if num is None`,
but several variants are also valid: `if num is not None`, `if num ==
None`, `if isinstance(num, int)`. Since this is a pretty small space
of valid next lines, and all of them imply some understanding that
`num` may not be an `int`, we can use this program to test models for
nullability understanding by asking them to complete the program
another lines, then see if they produce something that matches these
valid lines with the regular expression
`num\s*(is\s*(not)?|==)\s*None|isinstance\(num`.]

This test is on the simpler side, but we can challenge the model more,
adding layers of indirection between the source and sink of nullable
values, testing the model's _interprocedural_ understanding.

We can also test how well models understand type annotations
separately; since the inclusion of type annotations in Python is not
required^[Technically this is known as "Optional typing", but that's
confusing in the context of this post. Not to be confused with Gradual
Typing, as introduced by Siek et al.], most of the Python code used as
training data operates in an untyped fashion, so models may understand
the dynamic flow of nullable values but not their static type
annotations. Test 5, below, tests the model's understanding of
`Optional` types annotations. The trailing colon makes a type
expression the only valid completion^[This is because function declarations with a
colon and no type, like `def fn(x:)` are not valid python. Since we’ve
already seen a usage of `get_square` that is passed a None value, it
wouldn’t be type-valid to complete the program with just `int`. So a
model can be tested on its understanding of `Optional` annotations by
seeing if its completion of the partial program includes
`Optional[int]`.]

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

All of the tests in this benchmark suite are composed of three
functions or less, where the largest function is seven lines long.

We measure the difficulty of these tests by measuring how
models of different sizes perform. We pay particular focus to
the Pythia model suite[@biderman23], as they have checkpoints available across
training runs and various scales. For measuring performance at larger sizes,
we've included Qwen2.5-Coder-32B\AT{cite}, Llama 3.1 405B Instruct\AT{cite}, and
DeepSeek-V3 (671B)\AT{cite}. Below, you can see the number of passing tests for
each model.
\todo{more through exploration of why?}

![A bar graph showing how several sizes of model perform on the
 high-level nullability tests](images/hl_model_results.svg){#fig:hl_scale}

In [@Fig:hl_scale], we can see the number of passing tests for each
model. We can see that generally models get better with scale.
\todo{I don't think this footnote is clear enough to add anything}
^[Pythia
12b performs worse than its 6.9b variant, though this
might be due to under-training at that size. Qwen 32B also performs
about as well as Pythia 6.9b, it's not clear if this is due to model
architecture or something else.]
Model performance on these tests is
approximately logarithmic in model size: models of 2.8 billion
parameters can pass about half the tests, but it takes more than 405
billion parameters to pass all of the tests.
\todo{interesting observation; seems to me that this is actually the case for all post-training evals. hmm, acutally it's also the case for pretraining loss --- see classic scaling laws papers: Kaplan et al, Chincilla, etc}

Next, we want to understand the training dynamics at play here.
143000. Below we can see how Pythia 6.9b performs on the tests during
training from step 2 to 143000:\todo{let's use the same axes scaling at the tigges paper}

![A line graph showing how the performance of the Pythia
6.9 model changes during training](images/hl_revision_results.svg){#fig:hl_time}

Again, performance does not increase monotonically.
This plot is quite noisy, so in the sequel, we will
show smoothed^[rolling average with a window size of 5] charts.


## Local vs Non-Local Type Correctness {#sec:grok}

For most of our tests, writing correct code simply requires following
the rules of Python's mypy type system. This type system requires that
types be internally consistent within functions, and match function
type signatures if they exist. But six of our tests are different,
because they involve functions that are *not* annotated with type
signatures. Under mypy, these functions are allowed to do almost
anything with their types. But at runtime, using values of the wrong
type with these functions will result in a type error.

\AT{too many clauses!}
You could strengthen mypy's type rules to require that these untyped
functions have some valid type they could be assigned which would
cause the function to typecheck. This would prevent programs that pass
the typechecker from having runtime type errors. We can call this
strengthened type system mypy+.

Since mypy+ has strictly more typing rules than mypy, we would expect
the model to take longer to learn how to satisfy it. And indeed this
is the case: We find that models learn to satisfy the mypy typechecker

One explanation of why the model gets worse before it gets better is that the
model first learns the concepts need to solve the task, then learns the
language of python --- its syntax, static (under mypy), and dynamic semantics,
and then both.
\AT{cite something here. grokking, double descent, interp?}
Let's make this more concrete.

We say a model produces an answer that is "morally" (vs technically) correct if
the code attempts to solve the problem asked of it. Each test case is paired with a
regex that tests if the model output produces code that touches all of the relevant
concepts.
\AS{put an example here?}
Here, we say the solution is
"technically" correct if it passes `mypy`.

![A graph showing how often the Pythia 6.9b produces code that
typechecks on the tests, vs produces code that shows true
understanding.](images/hl_mypy_vs_grep.svg){#fig:hl_moral}

# Measuring Nullability Understanding Internally {#sec:probing}
\todo{write this section}
## Designing Prompts to Extract Nullability Activations

\todo{we can probably just make this a brief part of the related work}
At this point, we’ve figured out how to roughly measure nullability
understanding in the output of various language models, but we still
don’t know what their internal representations might look like or when
they emerge. To do this, we’re going to bring in some ideas described
in Zhou et al’s paper [“Representation Engineering: A Top-Down Approach
to AI Transparency”](https://arxiv.org/abs/2310.01405).

As language models predict each token in a text, they run their tuned
circuits over all the previous text. Tokens are first embedded into a
high-dimensional “token space”, and each layer of the transformer
model is made up of many parallel circuits which transform the
previous layers output into new embeddings in a new space. Each layer
can look not just at the output of the layer directly previous, but
actually all previous layers, through a channel called a residual
stream.

The paper presents two main approaches to interpreting a language
model; circuit-based, and representation-based. Circuit based
interpretability aims to pair down the network to a key set of
circuits which are sufficient to complete a particular task; this
allows practitioners to point to a particular part of the model and
say “this is where \<task\> is done”, much like neuroscientists assign
functionality to different parts of our brain.

On the other hand, representation-based interpretability looks at the
activation values across the network, and how they vary based on
different inputs, to extract “representations” of particular
concepts. The paper shows how representations can be extracted for
concepts like “happiness”, “honesty”, and “fairness”. First, they
construct many prompts which cause the model to act in a way aligned
with the concept, and many which cause the model to act in a way
aligned against the concept. For instance, they might prompt the model
with “Pretend you’re a dishonest person. The Eiffel Tower is” and
“Pretend you’re an honest person. The Eiffel Tower isr”. Then, they
take the internal activations which correspond to each, and try to
extract a high-dimensional vector which points towards the states
which are aligned, and away from the states that are not aligned. This
vector can then be used as a linear model to measure how much of the
concept is present in the model at any given time (for honesty, this
can be a lie-detector). They can also use it, and similar techniques,
to control the amount of the concept in a response, making it more or
less honest, or more or less fair.

![An excerpt from Zhou et al showing the reading outputs for several
 concepts](images/zhou.png)

In our setting, we were able to avoid dealing with the ambiguities of
natural language by only prompting with code. We decided to stick to
analyzing the nullability of individual variable occurrences, instead
of analyzing every expression. Specifically, we tried to capture the
concept “the variable I just generated refers to an nullable
quantity”, so our prompts looked like:

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

To generate these kinds of prompts, we started by asking a few
different chat models to generate for us programs that made use of
nullability . We prompted each model with:

> Generate me 100 typed python programs that use the Optional type,
> along with type annotations for any undefined functions that they
> use. Make sure that the programs are unique, and each involves at
> least eight lines of logic. Number each program from 1 to 100. Please
> put all the programs in a single file, with a main function that tests
> each. Don't include any text before or after the code, just the
> code. I will be using mypy with the --strict option to check the code.

We queried o1, o1-mini, deepseek-coder, and claude-sonnet using this
prompt, and then combined programs from the output of all of them into
a single file. Then, we took every function and class in the resulting
code file, and created a file with it and any recursive dependencies
and imports from the file. Finally, we took each variable read
occurrence in each function, and generated a prompt with the tokens up
to and including that variable read, and labeled it with whether or
not the mypy-inferred type is an Optional.

## Reading Vector Extraction

To start, let's look at how previous works have extracted reading
vectors from sample activations. In the Zhou representation
engineering paper, the authors extract a reading vector from the
contrastive pairs of activations using principal component
analysis (PCA).

First, they take each pair of honest and dishonest promptings for the
same stimulus, and get the difference between them, creating a set of
contrast vectors. They randomly flip some of these contrast vectors,
so that overall the set will vary a lot along the direction of the
contrast.  Since PCA assumes that the data is centered around the
origin, they then took the mean of all these vectors, and translated
all the vectors backwards along the mean vector, to create a set with
the same variances but centered around the origin.

Next, they use the PCA analysis from the sklearn library to get a set
of “component” vectors, where the vectors are orthogonal to each other
and explain the maximum variance of the samples in each prefix of the
list. Components in PCA are bidirectional (they can come out of the
analysis in either reflection, and both are equally correct), so next
they flip any component vectors that are pointing more towards the
negative samples than the positive samples. Then, they take the first
component, the most important one, and use it as their reading vector.

Our method for prompt generation didn’t admit contrastive pairs like
in the previous methods, but instead just a bunch of unconnected
positive and negative examples. So instead of doing PCA on contrast
vectors, we averaged the positive examples and the negative examples,
and then took the difference of the averages as our base reading
vector. This is called "mass mean probing" in the literature, and
empirically has been shown to generalize better in high dimensional
space than trying to learn a linear model through logistic
regression.^[see the appendix section "Mass Mean Probing vs Linear
Regression" for more on this]

In this reading vector, the impact of each layer based on the
magnitude of difference in that layer, instead of separate a notion of
how "important" that layer is to differentiating positive and negative
examples. So we decided to try a few different methods of normalizing
these layers to improve their overall accuracy as a linear model:

* No normalization; just the projection across the average difference.
* Normalizing each layers vector to a uniform length
* Dividing by the average amount that each layer activates on the positives samples
* Dividing by the average absolute amount that each layer activates on the positive samples
* Dividing by the square root of the average of squares of layer activations

And we found that no normalization actually did the best of all three
scaling methods. In domains like this one where we have a lot less
training data points then dimensions, what techniques will generalize
well to the test data can be hard to predict.

Prior work focused their probing on a single layer, often handpicked
based on prior papers. In our experiments, we decided to probe *all*
layers using a mass means probe, and learn which ones were most
important from the data. We tested two methods for doing so - either
allowing the magnitude of the difference of means vector to determine
the importance of the layer in the final probe, or to learn
coefficients for each layer using linear regression. We found that
which method is more accurate on test data varies over both model size
and number of training steps.

![The performance of pure mass means probing vs mass means probing
 with linear regression for different Pythia model sizes. Binary-cross
 entropy is plotted, so lower is
 better.](images/mm-vs-mmlr.svg){#fig:mm-vs-mmlr-sizes}

In [@Fig:mm-vs-mmlr-sizes], we can see that pure mass means probing
gives lower loss for smaller models (those with less than 410 million
parameters), but that for larger models weighting layers using linear
regression gives lower loss consistently.

![The performance of the two probing methods on the Pythia 160m model
 for different numbers of pretraining steps. There are regions where
 pure mass means scaling is better, and regions where linear
 regression on layer weights is better.](images/mm-vs-mmlr-160m.svg){#fig:mm-vs-mmlr-160m}

In [@Fig:mm-vs-mmlr-160m;@Fig:mm-vs-mmlr-410], we look at how these
scaling methods perform for different amounts of pretraining, for the
model sizes nearest the boundary. We see that relative merit of each
scaling method can vary significantly over pretraining steps.

![The performance of the two probing methods on the Pythia 410m model
for different numbers of pretraining steps. Pure mass means probing
starts better, but is quickly overtaken by mass means probing with
linear regression on layer weights.](images/mm-vs-mmlr-410m.svg){#fig:mm-vs-mmlr-410}

# Nullability Prediction Accuracy Across Training and Scale {#sec:results}

In this section, we study the performance of our nullability probes across time
and scale [@tigges24].
We use a mass-means probe [@li24] on all layers,
with a linear regression determining the weights of each layer.
@li24 and @zhou23 suggest that mass means probes are best for reading,
while the direction perpendicular to the separating hyperplane is best for
intervention.
However, previous work leaves open the question of cross-layer weights. We use
LR on the cross-layer weights because that is the probing method that we found
works best overall.
\AT{see section/appendix for further discussion}
While we
measured accuracy for every available Pythia model size, we exclude
the smallest (14m) from this plot since it would
exist entirely above the top of the plot.

![The performance, measured in binary cross-entropy, of each Pythia
 model size during pretraining. Since this graph is of loss, lower is
 better](images/accuracy_during_pretraining.svg){#fig:models-and-steps}

In [@Fig:models-and-steps], we plot loss against scale and time.
As expected, we see that loss tends to decreases as models get bigger and are
trained for longer. However, models with fewer than 1 billion parameters reach
their minimum loss well before the end of training. This may be because the
features beyond this point become more complex --- less linear, or the represented
features themselves represent more subtle concepts. \AT{speculation}

# Related Work

\AT{mention the tigges paper on circuits across scale, the feng and steinhardt papers, etc}

As previously discussed, [“Representation Engineering: A Top-Down
Approach to AI Transparency”](https://arxiv.org/abs/2310.01405) by
Zhou et al is the most closely related work, consolidating some
research on representation interpretability with linear probes. We
apply similar techniques, but to program semantics and dataflow
instead of natural language.

Several techniques exist for constructing linear probes, but after
experimental measurement we followed the mass means probing from [The
Geometry of Truth: Emergent Linear Structure in Large Language Model
Representations of True/False
Datasets](https://openreview.net/forum?id=CeJEfNKstt) by Marks and
Tegmark. The paper discusses several reasons why mass mean probing
might outperform linear regression.


# References {.unnumbered}
::: {#refs}
:::
